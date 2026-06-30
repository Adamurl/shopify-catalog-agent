from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audits.catalog_analysis import analyze_catalog_titles
from src.reports.title_suggestion_report import (
    build_title_suggestion_report,
    write_title_suggestions_csv,
)
from src.shopify.snapshot import load_products_from_snapshot

DEFAULT_INPUT_PATH = Path("data/raw/products.json")
DEFAULT_OUTPUT_PATH = Path("data/reports/title_suggestions.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic product title suggestions for manual review."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Product snapshot JSON path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Title suggestion CSV output path.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help=(
            "Only include products matching this category, collection, product type, "
            "or tag. Repeat for multiple categories."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        products = load_products_from_snapshot(args.input)
        products = _filter_active_products(products)
        products = _filter_products_by_categories(products, args.category)
        analysis = analyze_catalog_titles(products)
        report = build_title_suggestion_report(products)
        write_title_suggestions_csv(report.rows, args.output)
    except Exception as exc:
        print(f"Title suggestion report failed: {exc}")
        return 1

    print("Title suggestion report complete")
    if args.category:
        print(f"Category filter: {', '.join(args.category)}")
    print(f"Products reviewed: {report.total_products_reviewed}")
    print(f"Suggestions generated: {report.total_suggestions_generated}")
    print(f"Low-confidence rows: {report.low_confidence_rows}")
    print(f"Missing product types: {analysis.missing_product_types}")
    print(f"Missing tags: {analysis.missing_tags}")
    print(f"CSV report: {args.output}")
    print("")
    print("Top detected families:")
    for family, count in list(report.family_counts.items())[:10]:
        print(f"- {family}: {count}")

    return 0


def _filter_active_products(products):
    return [product for product in products if product.status == "ACTIVE"]


def _filter_products_by_categories(products, categories: list[str]):
    if not categories:
        return products

    normalized_categories = [_normalize_filter_value(category) for category in categories]
    return [
        product
        for product in products
        if any(
            _product_matches_category(product, category)
            for category in normalized_categories
        )
    ]


def _product_matches_category(product, category: str) -> bool:
    values = [
        product.category,
        product.product_type,
        *product.collections,
        *product.tags,
    ]
    for value in values:
        normalized_value = _normalize_filter_value(value)
        if normalized_value and (
            normalized_value == category
            or category in normalized_value
            or normalized_value in category
        ):
            return True
    return False


def _normalize_filter_value(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("|", " ").split())


if __name__ == "__main__":
    raise SystemExit(main())
