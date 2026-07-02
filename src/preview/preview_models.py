from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

APPROVAL_PENDING = "PENDING"
ALLOWED_APPROVAL_VALUES = {"PENDING", "APPROVED", "REJECTED", "REVIEW"}


@dataclass(frozen=True)
class PreviewCurrentValues:
    title: str
    handle: str
    seo_title: str
    seo_description: str
    description_html: str
    first_image_alt: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreviewSuggestedValues:
    title: str
    handle: str
    seo_title: str
    seo_description: str
    description_html: str
    first_image_alt: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreviewRow:
    approval: str
    product_id: str
    status: str
    inventory: int | None
    current: PreviewCurrentValues
    suggested: PreviewSuggestedValues
    tags_to_append: list[str]
    detected_family: str | None
    detected_subgroup: str | None
    detected_attributes: dict[str, Any]
    confidence: float
    warnings: list[str]
    blocked_fields: list[str]
    rule_id: str
    rule_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval": self.approval,
            "product_id": self.product_id,
            "status": self.status,
            "inventory": self.inventory,
            "current": self.current.to_dict(),
            "suggested": self.suggested.to_dict(),
            "tags_to_append": self.tags_to_append,
            "detected_family": self.detected_family,
            "detected_subgroup": self.detected_subgroup,
            "detected_attributes": self.detected_attributes,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "blocked_fields": self.blocked_fields,
            "rule_id": self.rule_id,
            "rule_status": self.rule_status,
        }


@dataclass(frozen=True)
class PreviewDocument:
    preview_id: str
    created_at: str
    mode: str
    rule_id: str
    rule_status: str
    group: str
    products_count: int
    rows: list[PreviewRow]

    def to_dict(self) -> dict[str, Any]:
        return {
            "preview_id": self.preview_id,
            "created_at": self.created_at,
            "mode": self.mode,
            "rule_id": self.rule_id,
            "rule_status": self.rule_status,
            "group": self.group,
            "products_count": self.products_count,
            "rows": [row.to_dict() for row in self.rows],
        }

