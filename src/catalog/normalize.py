from __future__ import annotations

from typing import Any

from src.catalog.models import CatalogImage, CatalogProduct, CatalogVariant
from src.catalog.utils import clean_text, html_to_text


def normalize_products(raw_products: list[dict[str, Any]]) -> list[CatalogProduct]:
    """Convert Shopify product nodes into the local canonical catalog shape."""
    return [normalize_product(product) for product in raw_products]


def normalize_product(node: dict[str, Any]) -> CatalogProduct:
    seo = node.get("seo") or {}
    category = node.get("category") or {}
    images = _normalize_images(node)
    variants = _normalize_variants(node)
    inventory_values = [
        variant.inventory_quantity
        for variant in variants
        if variant.inventory_quantity is not None
    ]
    total_inventory = sum(inventory_values) if inventory_values else None

    return CatalogProduct(
        id=clean_text(node.get("id")),
        title=clean_text(node.get("title")),
        handle=clean_text(node.get("handle")),
        status=clean_text(node.get("status") or "UNKNOWN"),
        vendor=clean_text(node.get("vendor")) or None,
        product_type=clean_text(node.get("productType")) or None,
        category=clean_text(category.get("name")) or None,
        collections=_collection_titles(node),
        tags=[clean_text(tag) for tag in node.get("tags") or [] if clean_text(tag)],
        seo_title=clean_text(seo.get("title")) or None,
        seo_description=clean_text(seo.get("description")) or None,
        description_html=node.get("descriptionHtml"),
        description_text=html_to_text(node.get("descriptionHtml")),
        images=images,
        first_image_alt=images[0].alt if images else None,
        variants=variants,
        total_inventory=total_inventory,
        is_in_stock=any((value or 0) > 0 for value in inventory_values),
        created_at=node.get("createdAt"),
        updated_at=node.get("updatedAt"),
    )


def _connection_nodes(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    edges = (connection or {}).get("edges") or []
    return [edge.get("node") or {} for edge in edges]


def _collection_titles(node: dict[str, Any]) -> list[str]:
    return [
        clean_text(collection.get("title"))
        for collection in _connection_nodes(node.get("collections"))
        if clean_text(collection.get("title"))
    ]


def _normalize_images(node: dict[str, Any]) -> list[CatalogImage]:
    images: list[CatalogImage] = []
    seen: set[str] = set()

    for media in _connection_nodes(node.get("media")):
        image = media.get("image") or {}
        image_id = clean_text(media.get("id") or image.get("id"))
        if not image_id or image_id in seen:
            continue
        seen.add(image_id)
        images.append(
            CatalogImage(
                id=image_id,
                url=clean_text(image.get("url") or image.get("src")),
                alt=clean_text(image.get("altText") or media.get("alt")) or None,
            )
        )

    for image in _connection_nodes(node.get("images")):
        image_id = clean_text(image.get("id"))
        if not image_id or image_id in seen:
            continue
        seen.add(image_id)
        images.append(
            CatalogImage(
                id=image_id,
                url=clean_text(image.get("url") or image.get("src")),
                alt=clean_text(image.get("altText")) or None,
            )
        )
    return images


def _normalize_variants(node: dict[str, Any]) -> list[CatalogVariant]:
    variants: list[CatalogVariant] = []
    for variant in _connection_nodes(node.get("variants")):
        variants.append(
            CatalogVariant(
                id=clean_text(variant.get("id")),
                title=clean_text(variant.get("title")),
                sku=clean_text(variant.get("sku")) or None,
                inventory_quantity=variant.get("inventoryQuantity"),
            )
        )
    return variants
