from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProductVariant:
    id: str
    title: str
    sku: str | None
    barcode: str | None
    inventory_quantity: int | None
    selected_options: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_shopify_node(cls, node: dict[str, Any]) -> "ProductVariant":
        selected_options = {
            option.get("name", ""): option.get("value", "")
            for option in node.get("selectedOptions", [])
            if option.get("name")
        }
        return cls(
            id=node.get("id", ""),
            title=node.get("title", ""),
            sku=node.get("sku"),
            barcode=node.get("barcode"),
            inventory_quantity=node.get("inventoryQuantity"),
            selected_options=selected_options,
        )


@dataclass(frozen=True)
class ProductMedia:
    id: str
    url: str | None
    alt_text: str | None

    @classmethod
    def from_shopify_node(cls, node: dict[str, Any]) -> "ProductMedia":
        image = node.get("image") or {}
        return cls(
            id=node.get("id", ""),
            url=image.get("url"),
            alt_text=image.get("altText") or node.get("alt"),
        )


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    handle: str
    vendor: str | None
    product_type: str | None
    category: str | None
    tags: list[str]
    status: str | None
    seo_title: str | None
    seo_description: str | None
    description_html: str | None
    collections: list[str]
    variants: list[ProductVariant]
    options: list[dict[str, Any]]
    media: list[ProductMedia]

    @classmethod
    def from_shopify_node(cls, node: dict[str, Any]) -> "Product":
        category = node.get("category") or {}
        seo = node.get("seo") or {}
        collections = [
            edge.get("node", {}).get("title", "")
            for edge in node.get("collections", {}).get("edges", [])
            if edge.get("node", {}).get("title")
        ]
        variants = [
            ProductVariant.from_shopify_node(edge.get("node", {}))
            for edge in node.get("variants", {}).get("edges", [])
        ]
        media = [
            ProductMedia.from_shopify_node(edge.get("node", {}))
            for edge in node.get("media", {}).get("edges", [])
        ]
        return cls(
            id=node.get("id", ""),
            title=node.get("title", ""),
            handle=node.get("handle", ""),
            vendor=node.get("vendor"),
            product_type=node.get("productType"),
            category=category.get("name"),
            tags=list(node.get("tags") or []),
            status=node.get("status"),
            seo_title=seo.get("title"),
            seo_description=seo.get("description"),
            description_html=node.get("descriptionHtml"),
            collections=collections,
            variants=variants,
            options=list(node.get("options") or []),
            media=media,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["productType"] = data.pop("product_type")
        data["seo"] = {
            "title": data.pop("seo_title"),
            "description": data.pop("seo_description"),
        }
        data["descriptionHtml"] = data.pop("description_html")
        return data

    @property
    def skus(self) -> list[str]:
        return [variant.sku for variant in self.variants if variant.sku]

    @property
    def barcodes(self) -> list[str]:
        return [variant.barcode for variant in self.variants if variant.barcode]

    @property
    def inventory_quantity(self) -> int | None:
        quantities = [
            variant.inventory_quantity
            for variant in self.variants
            if variant.inventory_quantity is not None
        ]
        return sum(quantities) if quantities else None
