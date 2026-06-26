from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from src.models.product import Product


@dataclass(frozen=True)
class CatalogSummary:
    total_products: int
    products_by_product_type: dict[str, int]
    products_by_vendor: dict[str, int]
    products_missing_product_type: int
    products_missing_tags: int
    products_missing_seo_title: int
    products_missing_meta_description: int
    products_missing_descriptions: int
    products_missing_images: int
    products_missing_image_alt_text: int
    products_missing_collections: int
    products_missing_sku: int
    duplicate_titles: list[str]
    duplicate_handles: list[str]

    def to_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {"metric": "Total products", "value": self.total_products},
            {
                "metric": "Products missing product type",
                "value": self.products_missing_product_type,
            },
            {"metric": "Products missing tags", "value": self.products_missing_tags},
            {
                "metric": "Products missing SEO title",
                "value": self.products_missing_seo_title,
            },
            {
                "metric": "Products missing meta description",
                "value": self.products_missing_meta_description,
            },
            {
                "metric": "Products missing descriptions",
                "value": self.products_missing_descriptions,
            },
            {"metric": "Products missing images", "value": self.products_missing_images},
            {
                "metric": "Products missing image alt text",
                "value": self.products_missing_image_alt_text,
            },
            {
                "metric": "Products missing collections",
                "value": self.products_missing_collections,
            },
            {"metric": "Products missing SKU", "value": self.products_missing_sku},
            {"metric": "Duplicate titles", "value": len(self.duplicate_titles)},
            {"metric": "Duplicate handles", "value": len(self.duplicate_handles)},
        ]
        rows.extend(
            {
                "metric": "Products by product type",
                "name": product_type,
                "value": count,
            }
            for product_type, count in self.products_by_product_type.items()
        )
        rows.extend(
            {"metric": "Products by vendor", "name": vendor, "value": count}
            for vendor, count in self.products_by_vendor.items()
        )
        return rows


def generate_catalog_summary(products: list[Product]) -> CatalogSummary:
    title_counts = _count_non_empty(product.title for product in products)
    handle_counts = _count_non_empty(product.handle for product in products)

    return CatalogSummary(
        total_products=len(products),
        products_by_product_type=_count_non_empty(
            product.product_type for product in products
        ),
        products_by_vendor=_count_non_empty(product.vendor for product in products),
        products_missing_product_type=sum(
            1 for product in products if not _has_text(product.product_type)
        ),
        products_missing_tags=sum(1 for product in products if not product.tags),
        products_missing_seo_title=sum(
            1 for product in products if not _has_text(product.seo_title)
        ),
        products_missing_meta_description=sum(
            1 for product in products if not _has_text(product.seo_description)
        ),
        products_missing_descriptions=sum(
            1 for product in products if not _has_text(product.description_html)
        ),
        products_missing_images=sum(1 for product in products if not product.media),
        products_missing_image_alt_text=sum(
            1
            for product in products
            if product.media
            and any(not _has_text(media.alt_text) for media in product.media)
        ),
        products_missing_collections=sum(
            1 for product in products if not product.collections
        ),
        products_missing_sku=sum(1 for product in products if not product.skus),
        duplicate_titles=_duplicates(title_counts),
        duplicate_handles=_duplicates(handle_counts),
    )


def write_summary_csv(summary: CatalogSummary, output_path: str) -> None:
    dataframe = pd.DataFrame(summary.to_rows())
    dataframe.to_csv(output_path, index=False)


def render_summary_markdown(summary: CatalogSummary) -> str:
    lines = [
        "# Catalog Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for row in summary.to_rows():
        if "name" in row:
            metric = f"{row['metric']}: {row['name']}"
        else:
            metric = row["metric"]
        lines.append(f"| {metric} | {row['value']} |")

    if summary.duplicate_titles:
        lines.extend(["", "## Duplicate Titles", ""])
        lines.extend(f"- {title}" for title in summary.duplicate_titles)
    if summary.duplicate_handles:
        lines.extend(["", "## Duplicate Handles", ""])
        lines.extend(f"- {handle}" for handle in summary.duplicate_handles)
    return "\n".join(lines) + "\n"


def write_summary_markdown(summary: CatalogSummary, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(render_summary_markdown(summary))


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _count_non_empty(values: Iterable[object]) -> dict[str, int]:
    counter = Counter(
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    )
    return dict(sorted(counter.items()))


def _duplicates(counter: Counter[str]) -> list[str]:
    return sorted(value for value, count in counter.items() if count > 1)
