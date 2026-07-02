from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CatalogImage:
    id: str
    url: str
    alt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogVariant:
    id: str
    title: str
    sku: str | None = None
    inventory_quantity: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogProduct:
    id: str
    title: str
    handle: str
    status: str
    vendor: str | None = None
    product_type: str | None = None
    category: str | None = None
    collections: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    seo_title: str | None = None
    seo_description: str | None = None
    description_html: str | None = None
    description_text: str = ""
    images: list[CatalogImage] = field(default_factory=list)
    first_image_alt: str | None = None
    variants: list[CatalogVariant] = field(default_factory=list)
    total_inventory: int | None = None
    is_in_stock: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["images"] = [image.to_dict() for image in self.images]
        data["variants"] = [variant.to_dict() for variant in self.variants]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogProduct":
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            handle=str(data.get("handle") or ""),
            status=str(data.get("status") or ""),
            vendor=data.get("vendor"),
            product_type=data.get("product_type"),
            category=data.get("category"),
            collections=list(data.get("collections") or []),
            tags=list(data.get("tags") or []),
            seo_title=data.get("seo_title"),
            seo_description=data.get("seo_description"),
            description_html=data.get("description_html"),
            description_text=str(data.get("description_text") or ""),
            images=[
                CatalogImage(
                    id=str(image.get("id") or ""),
                    url=str(image.get("url") or ""),
                    alt=image.get("alt"),
                )
                for image in data.get("images") or []
            ],
            first_image_alt=data.get("first_image_alt"),
            variants=[
                CatalogVariant(
                    id=str(variant.get("id") or ""),
                    title=str(variant.get("title") or ""),
                    sku=variant.get("sku"),
                    inventory_quantity=variant.get("inventory_quantity"),
                )
                for variant in data.get("variants") or []
            ],
            total_inventory=data.get("total_inventory"),
            is_in_stock=bool(data.get("is_in_stock")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

