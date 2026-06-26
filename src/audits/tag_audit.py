from __future__ import annotations

from dataclasses import dataclass

from src.models.product import Product


@dataclass(frozen=True)
class TagAuditFinding:
    product_id: str
    title: str
    issue: str


def audit_tags(products: list[Product]) -> list[TagAuditFinding]:
    return [
        TagAuditFinding(
            product_id=product.id,
            title=product.title,
            issue="Missing tags",
        )
        for product in products
        if not product.tags
    ]
