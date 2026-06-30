from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from src.models.product import Product


@dataclass(frozen=True)
class CatalogTitleAnalysis:
    total_products: int
    title_segment_patterns: dict[str, int]
    common_title_prefixes: dict[str, int]
    common_title_suffixes: dict[str, int]
    duplicate_titles: list[str]
    duplicate_handles: list[str]
    missing_product_types: int
    missing_tags: int

    def to_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {"metric": "Total products", "value": self.total_products},
            {"metric": "Missing product types", "value": self.missing_product_types},
            {"metric": "Missing tags", "value": self.missing_tags},
            {"metric": "Duplicate titles", "value": len(self.duplicate_titles)},
            {"metric": "Duplicate handles", "value": len(self.duplicate_handles)},
        ]
        rows.extend(
            {
                "metric": "Title segment pattern",
                "name": pattern,
                "value": count,
            }
            for pattern, count in self.title_segment_patterns.items()
        )
        rows.extend(
            {"metric": "Common title prefix", "name": prefix, "value": count}
            for prefix, count in self.common_title_prefixes.items()
        )
        rows.extend(
            {"metric": "Common title suffix", "name": suffix, "value": count}
            for suffix, count in self.common_title_suffixes.items()
        )
        return rows


def analyze_catalog_titles(products: list[Product]) -> CatalogTitleAnalysis:
    title_counts = _count_non_empty(product.title for product in products)
    handle_counts = _count_non_empty(product.handle for product in products)

    segment_patterns: Counter[str] = Counter()
    prefixes: Counter[str] = Counter()
    suffixes: Counter[str] = Counter()

    for product in products:
        title = product.title.strip()
        if not title:
            continue

        segments = [segment.strip() for segment in title.split(" - ")]
        segment_count = len(segments)
        segment_patterns[f"{segment_count} segment{'s' if segment_count != 1 else ''}"] += 1
        if segments[0]:
            prefixes[segments[0]] += 1
        if segments[-1]:
            suffixes[segments[-1]] += 1

    return CatalogTitleAnalysis(
        total_products=len(products),
        title_segment_patterns=_sorted_counter(segment_patterns),
        common_title_prefixes=_sorted_counter(prefixes),
        common_title_suffixes=_sorted_counter(suffixes),
        duplicate_titles=_duplicates(title_counts),
        duplicate_handles=_duplicates(handle_counts),
        missing_product_types=sum(
            1 for product in products if not _has_text(product.product_type)
        ),
        missing_tags=sum(1 for product in products if not product.tags),
    )


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _count_non_empty(values: Iterable[object]) -> Counter[str]:
    return Counter(
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    )


def _duplicates(counter: Counter[str]) -> list[str]:
    return sorted(value for value, count in counter.items() if count > 1)


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
