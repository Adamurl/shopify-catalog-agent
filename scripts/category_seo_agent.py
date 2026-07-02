from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.catalog.analyzer import analyze_catalog, filter_products
from src.catalog.classification_config import load_classification_config
from src.catalog.classification_reports import write_classification_outputs
from src.catalog.classifier import classify_products
from src.catalog.models import CatalogProduct
from src.catalog.reports import write_reports
from src.catalog.utils import latest_file, read_json, utc_timestamp
from src.shopify.client import ShopifyConfig, ShopifyGraphQLClient
from src.shopify.fetch_products import fetch_and_save_snapshots
from src.preview.preview_builder import build_previews, find_rule_paths
from src.preview.preview_reports import write_preview_outputs
from src.rules.rule_proposer import filter_classified_products, propose_rules
from src.rules.rule_reports import write_rule_reports
from src.writer.approved_row_loader import (
    find_expected_row,
    load_preview_row,
    require_approved,
)
from src.writer.safety_checks import build_update_from_row, validate_row_for_apply
from src.writer.shopify_writer import apply_product_update, fetch_product_snapshot
from src.writer.verification import expected_written_values, verify_snapshot
from src.writer.write_models import VerificationResult
from src.writer.writer_reports import write_verification_reports

SNAPSHOTS_DIR = Path("data/snapshots")
REPORTS_DIR = Path("data/reports")
CLASSIFIED_DIR = Path("data/classified")
PROPOSED_RULES_DIR = Path("data/rules/proposed")
APPROVED_RULES_DIR = Path("data/rules/approved")
PREVIEWS_DIR = Path("data/previews")

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ ONLY MODE Shopify catalog SEO audit and report tool."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "fetch",
        help="Fetch Shopify products and save raw plus normalized local snapshots.",
    )

    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze a normalized product snapshot and write local reports.",
    )
    analyze.add_argument(
        "--input",
        type=Path,
        help="Normalized products JSON path. Defaults to latest data/snapshots/normalized_products_*.json.",
    )
    analyze.add_argument("--category", help="Only analyze products in this Shopify category.")
    analyze.add_argument("--product-type", help="Only analyze this product type.")
    analyze.add_argument("--tag", help="Only analyze products with this tag.")
    analyze.add_argument("--collection", help="Only analyze products in this collection.")
    analyze.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include DRAFT and ARCHIVED products. Default analyzes ACTIVE products only.",
    )

    classify = subparsers.add_parser(
        "classify",
        help="Classify normalized products and write local read-only intelligence reports.",
    )
    classify.add_argument(
        "--snapshot",
        type=Path,
        help="Normalized products JSON path. Defaults to latest data/snapshots/normalized_products_*.json.",
    )
    classify.add_argument(
        "--config",
        type=Path,
        default=Path("data/config/classification_defaults.json"),
        help="Classification config JSON path.",
    )
    classify.add_argument("--category", help="Only classify products in this Shopify category.")
    classify.add_argument("--product-type", help="Only classify this product type.")
    classify.add_argument("--tag", help="Only classify products with this tag.")
    classify.add_argument("--collection", help="Only classify products in this collection.")
    classify.add_argument("--vendor", help="Only classify products from this vendor.")
    classify.add_argument(
        "--status",
        help="Only classify products with this status, such as ACTIVE, DRAFT, or ARCHIVED.",
    )
    classify.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include DRAFT and ARCHIVED products when --status is not provided. Default is ACTIVE only.",
    )

    propose = subparsers.add_parser(
        "propose-rules",
        help="Generate local proposed JSON cleanup rules from classified products.",
    )
    propose.add_argument(
        "--classified",
        type=Path,
        help="Classified products JSON path. Defaults to latest data/classified/classified_products_*.json.",
    )
    propose.add_argument("--family", help="Only propose rules for this family.")
    propose.add_argument("--subgroup", help="Only propose rules for this subgroup.")
    propose.add_argument("--product-type", help="Only propose rules for this product type.")
    propose.add_argument("--collection", help="Only propose rules for this collection.")
    propose.add_argument("--tag", help="Only propose rules for this tag.")
    propose.add_argument("--vendor", help="Only propose rules for this vendor.")
    propose.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="Minimum product confidence for input products and proposed rule match criteria.",
    )
    propose.add_argument(
        "--min-group-size",
        type=int,
        default=3,
        help="Minimum preferred group size. Smaller groups still produce proposed rules with warnings.",
    )

    preview = subparsers.add_parser(
        "preview",
        help="Render read-only product-by-product previews from classified products and rules.",
    )
    preview.add_argument(
        "--classified",
        type=Path,
        help="Classified products JSON path. Defaults to latest data/classified/classified_products_*.json.",
    )
    preview.add_argument("--rule", type=Path, help="Explicit proposed or approved rule JSON path.")
    preview.add_argument("--family", help="Only preview products in this family.")
    preview.add_argument("--subgroup", help="Only preview products in this subgroup.")
    preview.add_argument("--product-type", help="Only preview products in this product type.")
    preview.add_argument("--collection", help="Only preview products in this collection.")
    preview.add_argument("--tag", help="Only preview products with this tag.")
    preview.add_argument("--vendor", help="Only preview products from this vendor.")
    preview.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Only preview products at or above this classification confidence.",
    )
    preview.add_argument(
        "--approved-rules-only",
        action="store_true",
        help="Use only rules under data/rules/approved when --rule is not provided.",
    )

    apply_one = subparsers.add_parser(
        "apply-one",
        help="Apply exactly one APPROVED preview row to Shopify, then refetch and verify.",
    )
    apply_one.add_argument("--preview", type=Path, required=True, help="Preview CSV path.")
    apply_one.add_argument("--product-id", help="Shopify product GID to apply.")
    apply_one.add_argument(
        "--row-index",
        type=int,
        help="1-based preview data row index to apply.",
    )

    verify_one = subparsers.add_parser(
        "verify-one",
        help="Refetch one Shopify product and verify it against an expected preview CSV row.",
    )
    verify_one.add_argument("--product-id", required=True, help="Shopify product GID to verify.")
    verify_one.add_argument("--expected", type=Path, required=True, help="Preview CSV path.")

    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main() -> int:
    configure_logging()
    load_dotenv()
    args = parse_args()
    mode_label = "ONE PRODUCT TEST MODE" if args.command in {"apply-one", "verify-one"} else "READ ONLY MODE"
    LOGGER.info("%s: starting %s", mode_label, args.command)

    try:
        if args.command == "fetch":
            return run_fetch()
        if args.command == "analyze":
            return run_analyze(args)
        if args.command == "classify":
            return run_classify(args)
        if args.command == "propose-rules":
            return run_propose_rules(args)
        if args.command == "preview":
            return run_preview(args)
        if args.command == "apply-one":
            return run_apply_one(args)
        if args.command == "verify-one":
            return run_verify_one(args)
    except Exception as exc:
        LOGGER.exception("READ ONLY MODE: command failed")
        print(f"READ ONLY MODE: command failed: {exc}")
        return 1

    print(f"Unknown command: {args.command}")
    return 1


def run_fetch() -> int:
    config = ShopifyConfig.from_env()
    client = ShopifyGraphQLClient(config)
    timestamp = utc_timestamp()
    raw_path = SNAPSHOTS_DIR / f"raw_products_{timestamp}.json"
    normalized_path = SNAPSHOTS_DIR / f"normalized_products_{timestamp}.json"

    fetch_and_save_snapshots(client, raw_path=raw_path, normalized_path=normalized_path)

    print("READ ONLY MODE: fetch complete")
    print(f"Raw snapshot: {raw_path}")
    print(f"Normalized snapshot: {normalized_path}")
    return 0


def run_analyze(args: argparse.Namespace) -> int:
    input_path = args.input or latest_file(SNAPSHOTS_DIR, "normalized_products_*.json")
    if input_path is None:
        raise FileNotFoundError(
            "No normalized product snapshot found. Run "
            "`python scripts/category_seo_agent.py fetch` first."
        )

    products = load_normalized_products(input_path)
    filtered = filter_products(
        products,
        category=args.category,
        product_type=args.product_type,
        tag=args.tag,
        collection=args.collection,
        include_inactive=args.include_inactive,
    )
    analysis = analyze_catalog(filtered)
    timestamp = utc_timestamp()
    paths = write_reports(
        analysis,
        REPORTS_DIR,
        timestamp,
        filter_label=_filter_label(args, input_path),
    )

    print("READ ONLY MODE: analysis complete")
    print(f"Snapshot analyzed: {input_path}")
    print(f"Products analyzed: {analysis.total_products}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def run_classify(args: argparse.Namespace) -> int:
    input_path = args.snapshot or latest_file(SNAPSHOTS_DIR, "normalized_products_*.json")
    if input_path is None:
        raise FileNotFoundError(
            "No normalized product snapshot found. Run "
            "`python scripts/category_seo_agent.py fetch` first."
        )

    products = load_normalized_products(input_path)
    filtered = filter_products(
        products,
        category=args.category,
        product_type=args.product_type,
        tag=args.tag,
        collection=args.collection,
        vendor=args.vendor,
        status=args.status,
        include_inactive=args.include_inactive,
    )
    config = load_classification_config(args.config)
    classified = classify_products(filtered, config)
    timestamp = utc_timestamp()
    paths = write_classification_outputs(
        classified,
        CLASSIFIED_DIR,
        REPORTS_DIR,
        timestamp,
        config,
        filter_label=_filter_label(args, input_path),
    )

    print("READ ONLY MODE: classification complete")
    print(f"Snapshot classified: {input_path}")
    print(f"Products classified: {len(classified)}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def run_propose_rules(args: argparse.Namespace) -> int:
    input_path = args.classified or latest_file(CLASSIFIED_DIR, "classified_products_*.json")
    if input_path is None:
        raise FileNotFoundError(
            "No classified product snapshot found. Run "
            "`python scripts/category_seo_agent.py classify` first."
        )

    products = load_classified_products(input_path)
    filtered = filter_classified_products(
        products,
        family=args.family,
        subgroup=args.subgroup,
        product_type=args.product_type,
        collection=args.collection,
        tag=args.tag,
        vendor=args.vendor,
        min_confidence=args.min_confidence,
    )
    timestamp = utc_timestamp()
    result = propose_rules(
        filtered,
        PROPOSED_RULES_DIR,
        timestamp,
        min_confidence=args.min_confidence,
        min_group_size=args.min_group_size,
    )
    report_paths = write_rule_reports(
        result.rules,
        result.rule_paths,
        REPORTS_DIR,
        timestamp,
        filter_label=_filter_label(args, input_path),
    )

    print("READ ONLY MODE: rule proposal complete")
    print(f"Classified snapshot: {input_path}")
    print(f"Products considered: {len(filtered)}")
    print(f"Rules proposed: {len(result.rules)}")
    for rule_id, path in result.rule_paths.items():
        print(f"rule:{rule_id}: {path}")
    for name, path in report_paths.items():
        print(f"{name}: {path}")
    return 0


def run_preview(args: argparse.Namespace) -> int:
    input_path = args.classified or latest_file(CLASSIFIED_DIR, "classified_products_*.json")
    if input_path is None:
        raise FileNotFoundError(
            "No classified product snapshot found. Run "
            "`python scripts/category_seo_agent.py classify` first."
        )
    products = load_classified_products(input_path)
    filtered = filter_classified_products(
        products,
        family=args.family,
        subgroup=args.subgroup,
        product_type=args.product_type,
        collection=args.collection,
        tag=args.tag,
        vendor=args.vendor,
        min_confidence=args.min_confidence,
    )
    rule_paths = find_rule_paths(
        PROPOSED_RULES_DIR,
        APPROVED_RULES_DIR,
        explicit_rule=args.rule,
        approved_rules_only=args.approved_rules_only,
    )
    if not rule_paths:
        raise FileNotFoundError(
            "No rule JSON files found. Run "
            "`python scripts/category_seo_agent.py propose-rules` first."
        )
    timestamp = utc_timestamp()
    previews = build_previews(filtered, rule_paths, timestamp)
    paths = write_preview_outputs(previews, PREVIEWS_DIR, REPORTS_DIR, timestamp)

    print("READ ONLY MODE: preview complete")
    print(f"Classified snapshot: {input_path}")
    print(f"Products considered: {len(filtered)}")
    print(f"Rules rendered: {len(rule_paths)}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def run_apply_one(args: argparse.Namespace) -> int:
    row = load_preview_row(
        args.preview,
        product_id=args.product_id,
        row_index=args.row_index,
    )
    require_approved(row)
    warnings = validate_row_for_apply(row)
    update = build_update_from_row(row)

    client = ShopifyGraphQLClient(ShopifyConfig.from_env())
    started_at = _iso_now()
    before = fetch_product_snapshot(client, row.product_id)
    if before.status != "ACTIVE":
        raise ValueError(f"Refusing inactive live Shopify product: {before.status}")

    after = apply_product_update(client, update)
    mismatches = verify_snapshot(row, update, after)
    completed_at = _iso_now()
    result = VerificationResult(
        mode="ONE_PRODUCT_TEST",
        product_id=row.product_id,
        preview_file=row.preview_file,
        started_at=started_at,
        completed_at=completed_at,
        write_attempted=True,
        verification_passed=not mismatches,
        written_fields=update.written_fields,
        blocked_fields=row.blocked_fields,
        before=before.to_dict(),
        expected=expected_written_values(row, update),
        after=after.to_dict(),
        mismatches=mismatches,
        warnings=warnings,
    )
    timestamp = utc_timestamp()
    paths = write_verification_reports(result, REPORTS_DIR, timestamp)

    print("ONE PRODUCT TEST MODE: apply-one complete")
    print(f"Product ID: {row.product_id}")
    print(f"Written fields: {', '.join(update.written_fields)}")
    print(f"Verification passed: {result.verification_passed}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if result.verification_passed else 1


def run_verify_one(args: argparse.Namespace) -> int:
    row = find_expected_row(args.expected, args.product_id)
    warnings = validate_row_for_apply(row)
    update = build_update_from_row(row)

    client = ShopifyGraphQLClient(ShopifyConfig.from_env())
    started_at = _iso_now()
    after = fetch_product_snapshot(client, row.product_id)
    mismatches = verify_snapshot(row, update, after)
    completed_at = _iso_now()
    result = VerificationResult(
        mode="ONE_PRODUCT_TEST",
        product_id=row.product_id,
        preview_file=row.preview_file,
        started_at=started_at,
        completed_at=completed_at,
        write_attempted=False,
        verification_passed=not mismatches,
        written_fields=update.written_fields,
        blocked_fields=row.blocked_fields,
        before={},
        expected=expected_written_values(row, update),
        after=after.to_dict(),
        mismatches=mismatches,
        warnings=warnings,
    )
    timestamp = utc_timestamp()
    paths = write_verification_reports(result, REPORTS_DIR, timestamp)

    print("ONE PRODUCT TEST MODE: verify-one complete")
    print(f"Product ID: {row.product_id}")
    print(f"Verification passed: {result.verification_passed}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if result.verification_passed else 1


def load_normalized_products(path: Path) -> list[CatalogProduct]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Normalized snapshot must contain a list: {path}")
    return [CatalogProduct.from_dict(item) for item in data if isinstance(item, dict)]


def load_classified_products(path: Path) -> list[dict[str, object]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Classified snapshot must contain a list: {path}")
    return [item for item in data if isinstance(item, dict)]


def _filter_label(args: argparse.Namespace, input_path: Path) -> str:
    status = getattr(args, "status", None)
    if status:
        filters = [f"status={status}"]
    else:
        include_inactive = bool(getattr(args, "include_inactive", False))
        filters = ["ACTIVE products" if not include_inactive else "all statuses"]
    if getattr(args, "category", None):
        filters.append(f'category="{args.category}"')
    if getattr(args, "product_type", None):
        filters.append(f'product_type="{args.product_type}"')
    if getattr(args, "tag", None):
        filters.append(f'tag="{args.tag}"')
    if getattr(args, "collection", None):
        filters.append(f'collection="{args.collection}"')
    if getattr(args, "vendor", None):
        filters.append(f'vendor="{args.vendor}"')
    if getattr(args, "family", None):
        filters.append(f'family="{args.family}"')
    if getattr(args, "subgroup", None):
        filters.append(f'subgroup="{args.subgroup}"')
    if getattr(args, "min_confidence", None) is not None:
        filters.append(f"min_confidence={args.min_confidence}")
    filters.append(f"snapshot={input_path}")
    return ", ".join(filters)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
