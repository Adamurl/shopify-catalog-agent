from __future__ import annotations

from dataclasses import dataclass

from src.models.product import Product


@dataclass(frozen=True)
class CollectionAuditFinding:
    product_id: str
    title: str
    issue: str


def audit_collections(products: list[Product]) -> list[CollectionAuditFinding]:
    return [
        CollectionAuditFinding(
            product_id=product.id,
            title=product.title,
            issue="Missing collections",
        )
        for product in products
        if not product.collections
    ]
