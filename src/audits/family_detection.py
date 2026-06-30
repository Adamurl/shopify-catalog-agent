from __future__ import annotations

from dataclasses import dataclass

from src.models.product import Product

GENERIC_PRODUCT_TYPES = {
    "accessories",
    "general",
    "misc",
    "miscellaneous",
    "other",
    "product",
    "products",
}

KNOWN_FAMILIES = [
    "Ayoyotes with Obsidian",
    "Ayoyotes",
    "Macuahuitl",
    "Huaraches",
    "Abalone",
    "Atecocolli",
    "Copilli",
]


@dataclass(frozen=True)
class FamilyDetection:
    family: str
    source: str
    reason: str


def detect_product_family(product: Product) -> FamilyDetection:
    keyword_family = _match_known_family(product.title)
    product_type = (product.product_type or "").strip()

    if keyword_family:
        return FamilyDetection(
            family=keyword_family,
            source="keyword_match",
            reason=f"Matched known family keyword in title: {keyword_family}",
        )

    if product_type and not _is_generic_product_type(product_type):
        return FamilyDetection(
            family=product_type,
            source="product_type",
            reason=f"Used specific product type: {product_type}",
        )

    title_prefix = _title_prefix(product.title)
    if title_prefix:
        return FamilyDetection(
            family=title_prefix,
            source="title_prefix",
            reason=f"Used title prefix before first separator: {title_prefix}",
        )

    return FamilyDetection(
        family="Unknown",
        source="unknown",
        reason="No useful product type, known keyword, or title prefix found",
    )


def _match_known_family(title: str) -> str | None:
    normalized_title = title.casefold()
    for family in KNOWN_FAMILIES:
        if family.casefold() in normalized_title:
            return family
    return None


def _is_generic_product_type(product_type: str) -> bool:
    return product_type.strip().casefold() in GENERIC_PRODUCT_TYPES


def _title_prefix(title: str) -> str:
    return title.split(" - ", 1)[0].strip()
