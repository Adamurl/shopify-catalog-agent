from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.catalog.utils import read_json

DEFAULT_CLASSIFICATION_CONFIG_PATH = Path("data/config/classification_defaults.json")


@dataclass(frozen=True)
class ClassificationConfig:
    colors: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    audience_terms: list[str] = field(default_factory=list)
    gender_terms: dict[str, list[str]] = field(default_factory=dict)
    age_group_terms: dict[str, list[str]] = field(default_factory=dict)
    cultural_terms: list[str] = field(default_factory=list)
    use_case_keywords: dict[str, list[str]] = field(default_factory=dict)
    accessory_keywords: list[str] = field(default_factory=list)
    variant_keywords: list[str] = field(default_factory=list)
    family_keywords: dict[str, list[str]] = field(default_factory=dict)
    subgroup_keywords: dict[str, list[str]] = field(default_factory=dict)
    size_patterns: list[str] = field(default_factory=list)
    confidence_threshold: float = 0.65

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassificationConfig":
        return cls(
            colors=_string_list(data.get("colors")),
            materials=_string_list(data.get("materials")),
            audience_terms=_string_list(data.get("audience_terms")),
            gender_terms=_string_mapping(data.get("gender_terms")),
            age_group_terms=_string_mapping(data.get("age_group_terms")),
            cultural_terms=_string_list(data.get("cultural_terms")),
            use_case_keywords=_string_mapping(data.get("use_case_keywords")),
            accessory_keywords=_string_list(data.get("accessory_keywords")),
            variant_keywords=_string_list(data.get("variant_keywords")),
            family_keywords=_string_mapping(data.get("family_keywords")),
            subgroup_keywords=_string_mapping(data.get("subgroup_keywords")),
            size_patterns=_string_list(data.get("size_patterns")),
            confidence_threshold=float(data.get("confidence_threshold", 0.65)),
        )


def load_classification_config(
    path: Path = DEFAULT_CLASSIFICATION_CONFIG_PATH,
) -> ClassificationConfig:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Classification config must be a JSON object: {path}")
    return ClassificationConfig.from_dict(data)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _string_mapping(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    mapping: dict[str, list[str]] = {}
    for key, items in value.items():
        terms = _string_list(items)
        if str(key).strip() and terms:
            mapping[str(key).strip()] = terms
    return mapping

