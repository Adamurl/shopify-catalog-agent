from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.product import Product, ProductMedia, ProductVariant


def load_products_from_snapshot(input_path: Path) -> list[Product]:
    raw_products = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw_products, list):
        raise ValueError("Product snapshot must contain a list of products")
    return [_product_from_snapshot(item) for item in raw_products]


def _product_from_snapshot(item: Any) -> Product:
    if not isinstance(item, dict):
        raise ValueError("Product snapshot entries must be objects")

    seo = item.get("seo") or {}
    return Product(
        id=item.get("id", ""),
        title=item.get("title", ""),
        handle=item.get("handle", ""),
        vendor=item.get("vendor"),
        product_type=item.get("productType") or item.get("product_type"),
        category=item.get("category"),
        tags=list(item.get("tags") or []),
        status=item.get("status"),
        seo_title=seo.get("title") or item.get("seo_title"),
        seo_description=seo.get("description") or item.get("seo_description"),
        description_html=item.get("descriptionHtml") or item.get("description_html"),
        collections=list(item.get("collections") or []),
        variants=[
            _variant_from_snapshot(variant) for variant in item.get("variants") or []
        ],
        options=list(item.get("options") or []),
        media=[_media_from_snapshot(media) for media in item.get("media") or []],
    )


def _variant_from_snapshot(item: Any) -> ProductVariant:
    item = item if isinstance(item, dict) else {}
    return ProductVariant(
        id=item.get("id", ""),
        title=item.get("title", ""),
        sku=item.get("sku"),
        barcode=item.get("barcode"),
        inventory_quantity=item.get("inventory_quantity")
        or item.get("inventoryQuantity"),
        selected_options=dict(
            item.get("selected_options") or item.get("selectedOptions") or {}
        ),
    )


def _media_from_snapshot(item: Any) -> ProductMedia:
    item = item if isinstance(item, dict) else {}
    return ProductMedia(
        id=item.get("id", ""),
        url=item.get("url"),
        alt_text=item.get("alt_text") or item.get("altText"),
    )
