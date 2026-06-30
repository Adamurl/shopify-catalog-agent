from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shopify.client import ShopifyConfig, ShopifyGraphQLClient
from src.shopify.product_updates import (
    ProductMediaAltUpdate,
    ProductSeoUpdate,
    append_missing_tags,
    fetch_product_snapshot,
    update_product_media_alt,
    update_product_seo,
)

DEFAULT_INPUT_PATH = Path("data/reports/macuahuitls_seo_audit.csv")
DEFAULT_TAGS = {
    "Macuahuitl": [
        "Macuahuitl",
        "Aztec club",
        "Wooden macuahuitl",
        "Mexica",
        "Danza Azteca",
        "Ceremonial tool",
        "Cultural education",
    ],
    "Tecpatl": [
        "Tecpatl",
        "Obsidian blade",
        "Mexica",
        "Danza Azteca",
        "Ceremonial tool",
        "Cultural education",
    ],
}


@dataclass(frozen=True)
class SeoReportRow:
    product_id: str
    status: str
    inventory: int | None
    current_title: str
    suggested_title: str
    handle: str
    detected_family: str
    current_tags: list[str]
    suggested_seo_title: str
    suggested_seo_description: str

    @property
    def default_tags(self) -> list[str]:
        return DEFAULT_TAGS.get(self.detected_family, [self.detected_family])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or apply Shopify SEO updates for Macuahuitl products."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Macuahuitls SEO audit CSV path.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates to Shopify. Without this flag the script only previews.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update every selected row. Without this flag only one row is selected.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Maximum rows to select when --all is not set.",
    )
    parser.add_argument(
        "--product-id",
        help="Only select this Shopify product ID.",
    )
    parser.add_argument(
        "--family",
        action="append",
        default=["Macuahuitl"],
        help=(
            "Detected family to include. Defaults to Macuahuitl. Repeat to include "
            "Tecpatl or another report family."
        ),
    )
    parser.add_argument(
        "--include-out-of-stock",
        action="store_true",
        help="Include selected rows even when report inventory is zero or negative.",
    )
    parser.add_argument(
        "--update-title",
        action="store_true",
        help="Also update the visible Shopify product title.",
    )
    parser.add_argument(
        "--update-description",
        action="store_true",
        help="Also update the visible Shopify product description HTML.",
    )
    parser.add_argument(
        "--update-handle",
        action="store_true",
        help="Also update the Shopify product handle/URL slug.",
    )
    parser.add_argument(
        "--update-image-alt",
        action="store_true",
        help="Also update the first product image alt text.",
    )
    parser.add_argument(
        "--size",
        help='Only select rows with this size in the suggested title, such as 27".',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        rows = load_seo_report(args.input)
        selected_rows = select_rows(
            rows,
            families=args.family,
            product_id=args.product_id,
            include_out_of_stock=args.include_out_of_stock,
            update_all=args.all,
            limit=args.limit,
            size=args.size,
        )
        if not selected_rows:
            print("No matching Macuahuitls SEO rows found.")
            return 1

        if args.apply:
            client = ShopifyGraphQLClient(ShopifyConfig.from_env())
        else:
            client = None

        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        print(f"Rows selected: {len(selected_rows)}")
        print("")

        for row in selected_rows:
            planned_update = build_update(
                row,
                update_title=args.update_title,
                update_description=args.update_description,
                update_handle=args.update_handle,
            )
            planned_image_alt = (
                build_image_alt_text(row) if args.update_image_alt else None
            )
            print_preview(row, planned_update, planned_image_alt)

            if not args.apply:
                continue

            assert client is not None
            before = fetch_product_snapshot(client, row.product_id)
            if before.status != "ACTIVE":
                print(f"Skipping inactive Shopify product: {before.title}")
                continue

            live_update = build_update(
                row,
                existing_tags=before.tags,
                update_title=args.update_title,
                update_description=args.update_description,
                update_handle=args.update_handle,
            )
            after = update_product_seo(client, live_update)
            updated_media_alt = None
            if args.update_image_alt:
                if not before.media:
                    print(f"Skipping image alt update; no product media: {before.title}")
                else:
                    media_after = update_product_media_alt(
                        client,
                        ProductMediaAltUpdate(
                            product_id=row.product_id,
                            media_id=before.media[0].id,
                            alt_text=build_image_alt_text(row),
                        ),
                    )
                    updated_media_alt = media_after.alt_text
            print("Shopify write verified:")
            print(f"- Product title: {after.title}")
            print(f"- Handle: {after.handle}")
            print(f"- SEO title: {after.seo_title}")
            print(f"- SEO description: {after.seo_description}")
            if args.update_description:
                print(f"- Product description HTML: {after.description_html}")
            if updated_media_alt:
                print(f"- First image alt: {updated_media_alt}")
            print(f"- Tags: {', '.join(after.tags)}")
            print("")

    except Exception as exc:
        print(f"Macuahuitls SEO update failed: {exc}")
        return 1

    if not args.apply:
        print("Dry run complete. Re-run with --apply to write to Shopify.")
    return 0


def load_seo_report(path: Path) -> list[SeoReportRow]:
    with path.open(encoding="utf-8", newline="") as file:
        return [parse_report_row(row) for row in csv.DictReader(file)]


def parse_report_row(row: dict[str, str]) -> SeoReportRow:
    return SeoReportRow(
        product_id=row.get("Product ID", "").strip(),
        status=row.get("Status", "").strip(),
        inventory=parse_inventory(row.get("Inventory", "")),
        current_title=row.get("Current Title", "").strip(),
        suggested_title=row.get("Suggested Title", "").strip(),
        handle=row.get("Handle", "").strip(),
        detected_family=row.get("Detected Family", "").strip(),
        current_tags=parse_semicolon_values(row.get("Tags", "")),
        suggested_seo_title=row.get("Suggested SEO Title", "").strip(),
        suggested_seo_description=row.get("Suggested SEO Description", "").strip(),
    )


def parse_inventory(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_semicolon_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def select_rows(
    rows: list[SeoReportRow],
    families: Iterable[str],
    product_id: str | None,
    include_out_of_stock: bool,
    update_all: bool,
    limit: int,
    size: str | None = None,
) -> list[SeoReportRow]:
    normalized_families = {normalize_value(family) for family in families}
    selected = [
        row
        for row in rows
        if row.status == "ACTIVE"
        and row.product_id
        and row.suggested_seo_title
        and row.suggested_seo_description
        and normalize_value(row.detected_family) in normalized_families
        and (not product_id or row.product_id == product_id)
        and (not size or size in row.suggested_title)
        and (include_out_of_stock or (row.inventory is not None and row.inventory > 0))
    ]

    if update_all:
        return selected

    if limit < 1:
        raise ValueError("--limit must be at least 1")
    if not product_id:
        selected = sorted(selected, key=first_test_sort_key)
    return selected[:limit]


def build_update(
    row: SeoReportRow,
    existing_tags: list[str] | None = None,
    update_title: bool = False,
    update_description: bool = False,
    update_handle: bool = False,
) -> ProductSeoUpdate:
    tags = row.current_tags if existing_tags is None else existing_tags
    product_title = build_product_title(row)
    return ProductSeoUpdate(
        product_id=row.product_id,
        seo_title=build_seo_title(row),
        seo_description=build_seo_description(row),
        tags=append_missing_tags(tags, row.default_tags),
        title=product_title if update_title else None,
        description_html=(
            build_product_description_html(row) if update_description else None
        ),
        handle=build_product_handle(row) if update_handle else None,
    )


def print_preview(
    row: SeoReportRow,
    update: ProductSeoUpdate,
    image_alt_text: str | None = None,
) -> None:
    print(f"Product: {row.current_title}")
    print(f"Handle: {row.handle}")
    print(f"Product ID: {row.product_id}")
    print(f"Inventory: {row.inventory}")
    print(f"SEO title -> {update.seo_title}")
    print(f"SEO description -> {update.seo_description}")
    if update.title:
        print(f"Product title -> {update.title}")
    if update.handle:
        print(f"URL handle -> {update.handle}")
    if update.description_html:
        print(f"Product description HTML -> {update.description_html}")
    if image_alt_text:
        print(f"First image alt -> {image_alt_text}")
    print(f"Tags -> {', '.join(update.tags)}")
    print("")


def normalize_value(value: str) -> str:
    return " ".join(value.casefold().split())


def first_test_sort_key(row: SeoReportRow) -> int:
    return 1 if is_accessory_row(row) else 0


def is_accessory_row(row: SeoReportRow) -> bool:
    searchable_text = normalize_value(
        f"{row.current_title} {row.suggested_seo_title} {row.handle}"
    )
    accessory_markers = ["spare blade", "spare blades", "replacement blade"]
    return any(marker in searchable_text for marker in accessory_markers)


def build_product_description_html(row: SeoReportRow) -> str:
    if row.detected_family == "Macuahuitl":
        return (
            "<p>This is a handmade wooden macuahuitl inspired by Mexica ceremonial "
            "clubs.</p>"
            "<p>Each macuahuitl is handmade to order with a 6-8 week lead time. "
            "Finish, color, and detail placement can vary slightly from piece to "
            "piece.</p>"
        )
    if row.detected_family == "Tecpatl":
        return (
            f"<p>{row.suggested_title} is a handmade tecpatl-inspired item with "
            "obsidian-style detailing for display, ceremony, cultural education, "
            "or collecting.</p>"
            "<p>Each piece is handmade, so finish and details can vary slightly.</p>"
        )
    return (
        f"<p>{row.suggested_title} is handmade for display, ceremony, cultural "
        "education, or collecting.</p>"
    )


def build_product_title(row: SeoReportRow) -> str:
    if row.detected_family != "Macuahuitl":
        return row.suggested_title
    prefix = "Macuahuitl"
    if "(Aztec Club)" in row.current_title:
        prefix = "Macuahuitl (Aztec Club)"
    suggested_without_family = row.suggested_title
    if suggested_without_family.startswith("Macuahuitl - "):
        suggested_without_family = suggested_without_family[len("Macuahuitl - ") :]
    return f"{prefix} - {suggested_without_family}"


def build_seo_title(row: SeoReportRow) -> str:
    if row.detected_family == "Macuahuitl":
        return build_product_title(row)
    return row.suggested_seo_title


def build_seo_description(row: SeoReportRow) -> str:
    if row.detected_family == "Macuahuitl":
        return (
            f"{build_product_title(row)} handmade wooden macuahuitl inspired by "
            "Mexica ceremonial clubs. Handmade to order with a 6-8 week lead time."
        )
    return row.suggested_seo_description


def build_product_handle(row: SeoReportRow) -> str:
    return slugify(build_product_title(row))


def build_image_alt_text(row: SeoReportRow) -> str:
    design = extract_design(row)
    design_phrase = f" with {design} design" if design else ""
    return (
        f"{build_product_title(row)} handmade wooden macuahuitl{design_phrase}, "
        "wooden handle, and obsidian-style blade details."
    )


def extract_design(row: SeoReportRow) -> str:
    title = row.suggested_title
    if title.startswith("Macuahuitl - "):
        title = title[len("Macuahuitl - ") :]
    title = re.sub(r"\s+-\s+\d+\"$", "", title)
    return title.strip()


def slugify(value: str) -> str:
    value = value.replace('"', "")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return re.sub(r"-+", "-", value).casefold()


if __name__ == "__main__":
    raise SystemExit(main())
