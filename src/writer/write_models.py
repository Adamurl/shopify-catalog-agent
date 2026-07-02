from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApprovedPreviewRow:
    row_index: int
    preview_file: str
    approval: str
    product_id: str
    status: str
    inventory: int | None
    current_title: str
    suggested_title: str
    current_handle: str
    suggested_handle: str
    current_seo_title: str
    suggested_seo_title: str
    current_seo_description: str
    suggested_seo_description: str
    current_description: str
    suggested_description: str
    current_first_image_alt: str
    suggested_first_image_alt: str
    current_tags: list[str]
    suggested_tags: list[str]
    tags_to_append: list[str]
    detected_family: str
    detected_subgroup: str
    detected_attributes: dict[str, Any]
    confidence: float
    warnings: list[str]
    blocked_fields: list[str]
    rule_id: str
    rule_status: str

    def expected_values(self) -> dict[str, Any]:
        return {
            "title": self.suggested_title,
            "handle": self.suggested_handle,
            "seo_title": self.suggested_seo_title,
            "seo_description": self.suggested_seo_description,
            "description_html": self.suggested_description,
            "first_image_alt": self.suggested_first_image_alt,
            "tags": self.suggested_tags,
        }


@dataclass(frozen=True)
class ShopifyMediaSnapshot:
    id: str
    alt_text: str | None
    url: str | None

    @classmethod
    def from_node(cls, node: dict[str, Any]) -> "ShopifyMediaSnapshot":
        image = node.get("image") or {}
        return cls(
            id=str(node.get("id") or ""),
            alt_text=node.get("alt") or image.get("altText"),
            url=image.get("url"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShopifyProductSnapshot:
    id: str
    title: str
    handle: str
    status: str | None
    tags: list[str]
    seo_title: str | None
    seo_description: str | None
    description_html: str | None
    inventory_quantity: int | None
    media: list[ShopifyMediaSnapshot] = field(default_factory=list)

    @classmethod
    def from_node(cls, node: dict[str, Any]) -> "ShopifyProductSnapshot":
        seo = node.get("seo") or {}
        variants = node.get("variants", {}).get("edges", [])
        quantities = [
            edge.get("node", {}).get("inventoryQuantity")
            for edge in variants
            if edge.get("node", {}).get("inventoryQuantity") is not None
        ]
        media = [
            ShopifyMediaSnapshot.from_node(edge.get("node", {}))
            for edge in node.get("media", {}).get("edges", [])
        ]
        return cls(
            id=str(node.get("id") or ""),
            title=str(node.get("title") or ""),
            handle=str(node.get("handle") or ""),
            status=node.get("status"),
            tags=list(node.get("tags") or []),
            seo_title=seo.get("title"),
            seo_description=seo.get("description"),
            description_html=node.get("descriptionHtml"),
            inventory_quantity=sum(quantities) if quantities else None,
            media=media,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "status": self.status,
            "tags": self.tags,
            "seo_title": self.seo_title,
            "seo_description": self.seo_description,
            "description_html": self.description_html,
            "inventory_quantity": self.inventory_quantity,
            "first_image_alt": self.media[0].alt_text if self.media else None,
            "media": [media.to_dict() for media in self.media],
        }


@dataclass(frozen=True)
class OneProductUpdate:
    product_id: str
    written_fields: list[str]
    title: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    tags: list[str] | None = None
    description_html: str | None = None
    handle: str | None = None
    first_image_alt: str | None = None

    def to_product_input(self) -> dict[str, Any]:
        product_input: dict[str, Any] = {"id": self.product_id}
        if self.title is not None:
            product_input["title"] = self.title
        if self.seo_title is not None or self.seo_description is not None:
            product_input["seo"] = {
                "title": self.seo_title or "",
                "description": self.seo_description or "",
            }
        if self.tags is not None:
            product_input["tags"] = self.tags
        if self.description_html is not None:
            product_input["descriptionHtml"] = self.description_html
        if self.handle is not None:
            product_input["handle"] = self.handle
        return product_input


@dataclass(frozen=True)
class FieldMismatch:
    field: str
    expected: Any
    actual: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    mode: str
    product_id: str
    preview_file: str
    started_at: str
    completed_at: str
    write_attempted: bool
    verification_passed: bool
    written_fields: list[str]
    blocked_fields: list[str]
    before: dict[str, Any]
    expected: dict[str, Any]
    after: dict[str, Any]
    mismatches: list[FieldMismatch]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "product_id": self.product_id,
            "preview_file": self.preview_file,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "write_attempted": self.write_attempted,
            "verification_passed": self.verification_passed,
            "written_fields": self.written_fields,
            "blocked_fields": self.blocked_fields,
            "before": self.before,
            "expected": self.expected,
            "after": self.after,
            "mismatches": [mismatch.to_dict() for mismatch in self.mismatches],
            "warnings": self.warnings,
        }
