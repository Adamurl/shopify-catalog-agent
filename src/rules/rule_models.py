from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleMatch:
    family: str | None
    subgroup: str | None
    required_attributes: dict[str, Any] = field(default_factory=dict)
    exclude_if: dict[str, Any] = field(default_factory=lambda: {"is_accessory": True})
    min_product_confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleTemplates:
    title_pattern: str
    handle_pattern: str
    meta_title_pattern: str
    meta_description_pattern: str
    description_template: str
    image_alt_template: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleTags:
    append: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)
    replace_existing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleFields:
    update: list[str] = field(default_factory=lambda: ["title", "seo", "tags"])
    leave_alone: list[str] = field(
        default_factory=lambda: ["handle", "description", "image_alt"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleConstraints:
    max_seo_title_length: int = 60
    min_meta_description_length: int = 120
    max_meta_description_length: int = 160
    allow_handle_updates: bool = False
    allow_description_updates: bool = False
    allow_image_alt_updates: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleExample:
    product_id: str
    current_title: str
    detected_attributes: dict[str, Any]
    example_title: str
    example_meta_title: str
    example_meta_description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleConfidence:
    score: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposedRule:
    rule_id: str
    version: int
    status: str
    group: str
    family: str | None
    subgroup: str | None
    created_at: str
    match: RuleMatch
    templates: RuleTemplates
    tags: RuleTags
    fields: RuleFields
    constraints: RuleConstraints
    manual_review_conditions: list[str]
    examples: list[RuleExample]
    confidence: RuleConfidence
    product_count: int
    source_product_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "status": self.status,
            "group": self.group,
            "family": self.family,
            "subgroup": self.subgroup,
            "created_at": self.created_at,
            "match": self.match.to_dict(),
            "templates": self.templates.to_dict(),
            "tags": self.tags.to_dict(),
            "fields": self.fields.to_dict(),
            "constraints": self.constraints.to_dict(),
            "manual_review_conditions": self.manual_review_conditions,
            "examples": [example.to_dict() for example in self.examples],
            "confidence": self.confidence.to_dict(),
            "product_count": self.product_count,
            "source_product_ids": self.source_product_ids,
        }
