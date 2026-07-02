from __future__ import annotations

from pathlib import Path
from typing import Any

from src.catalog.utils import read_json
from src.preview.diff_utils import dedupe_preserve_order, slugify_handle, tags_to_append
from src.preview.preview_models import (
    APPROVAL_PENDING,
    PreviewCurrentValues,
    PreviewRow,
    PreviewSuggestedValues,
)
from src.rules.template_inferer import render_template

ClassifiedProduct = dict[str, Any]
RuleDict = dict[str, Any]


def load_rule(path: Path) -> RuleDict:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Rule file must contain a JSON object: {path}")
    return data


def product_matches_rule(product: ClassifiedProduct, rule: RuleDict) -> bool:
    classification = _classification(product)
    attributes = _attributes(product)
    match = _match(rule)

    family = match.get("family")
    subgroup = match.get("subgroup")
    if family and not _same(classification.get("family"), family):
        return False
    if subgroup and not _same(classification.get("subgroup"), subgroup):
        return False

    min_confidence = float(match.get("min_product_confidence") or 0.0)
    if float(classification.get("confidence") or 0.0) < min_confidence:
        return False

    for name, expected in (match.get("required_attributes") or {}).items():
        if not _same(attributes.get(name), expected):
            return False

    for name, expected in (match.get("exclude_if") or {}).items():
        if _same(classification.get(name), expected) or _same(attributes.get(name), expected):
            return False

    return True


def render_preview_row(product: ClassifiedProduct, rule: RuleDict) -> PreviewRow:
    attributes = _attributes(product)
    classification = _classification(product)
    templates = _templates(rule)
    constraints = _constraints(rule)
    current = _current_values(product)

    suggested_title = render_template(
        str(templates.get("title_pattern") or ""),
        attributes,
        title=current.title,
    )
    suggested_handle = slugify_handle(
        render_template(
            str(templates.get("handle_pattern") or ""),
            attributes,
            title=suggested_title,
        )
    )
    suggested_seo_title = render_template(
        str(templates.get("meta_title_pattern") or ""),
        attributes,
        title=suggested_title,
    )
    suggested_seo_description = render_template(
        str(templates.get("meta_description_pattern") or ""),
        attributes,
        title=suggested_title,
    )
    suggested_description = render_template(
        str(templates.get("description_template") or ""),
        attributes,
        title=suggested_title,
    )
    suggested_image_alt = render_template(
        str(templates.get("image_alt_template") or ""),
        attributes,
        title=suggested_title,
    )

    current_tags = [str(tag) for tag in product.get("tags", []) if str(tag).strip()]
    append_tags = [str(tag) for tag in (_tags(rule).get("append") or [])]
    suggested_tags = dedupe_preserve_order([*current_tags, *append_tags])
    append_only = tags_to_append(current_tags, suggested_tags)
    blocked = _blocked_fields(
        current=current,
        suggested_handle=suggested_handle,
        suggested_description=suggested_description,
        suggested_image_alt=suggested_image_alt,
        constraints=constraints,
    )

    return PreviewRow(
        approval=APPROVAL_PENDING,
        product_id=str(product.get("id") or ""),
        status=str(product.get("status") or ""),
        inventory=_inventory(product),
        current=current,
        suggested=PreviewSuggestedValues(
            title=suggested_title,
            handle=suggested_handle,
            seo_title=suggested_seo_title,
            seo_description=suggested_seo_description,
            description_html=suggested_description,
            first_image_alt=suggested_image_alt,
            tags=suggested_tags,
        ),
        tags_to_append=append_only,
        detected_family=_string_or_none(classification.get("family")),
        detected_subgroup=_string_or_none(classification.get("subgroup")),
        detected_attributes=attributes,
        confidence=float(classification.get("confidence") or 0.0),
        warnings=[],
        blocked_fields=blocked,
        rule_id=str(rule.get("rule_id") or ""),
        rule_status=str(rule.get("status") or ""),
    )


def _current_values(product: ClassifiedProduct) -> PreviewCurrentValues:
    return PreviewCurrentValues(
        title=str(product.get("title") or ""),
        handle=str(product.get("handle") or ""),
        seo_title=str(product.get("seo_title") or ""),
        seo_description=str(product.get("seo_description") or ""),
        description_html=str(product.get("description_html") or ""),
        first_image_alt=str(product.get("first_image_alt") or ""),
        tags=[str(tag) for tag in product.get("tags", []) if str(tag).strip()],
    )


def _blocked_fields(
    current: PreviewCurrentValues,
    suggested_handle: str,
    suggested_description: str,
    suggested_image_alt: str,
    constraints: dict[str, Any],
) -> list[str]:
    blocked: list[str] = []
    if suggested_handle and suggested_handle != current.handle and not constraints.get("allow_handle_updates", False):
        blocked.append("handle")
    if suggested_description and suggested_description != current.description_html and not constraints.get("allow_description_updates", False):
        blocked.append("description")
    if suggested_image_alt and suggested_image_alt != current.first_image_alt and not constraints.get("allow_image_alt_updates", False):
        blocked.append("image_alt")
    return blocked


def _inventory(product: ClassifiedProduct) -> int | None:
    value = product.get("total_inventory")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _classification(product: ClassifiedProduct) -> dict[str, Any]:
    value = product.get("classification")
    return value if isinstance(value, dict) else {}


def _attributes(product: ClassifiedProduct) -> dict[str, Any]:
    value = product.get("attributes")
    return value if isinstance(value, dict) else {}


def _match(rule: RuleDict) -> dict[str, Any]:
    value = rule.get("match")
    return value if isinstance(value, dict) else {}


def _templates(rule: RuleDict) -> dict[str, Any]:
    value = rule.get("templates")
    return value if isinstance(value, dict) else {}


def _tags(rule: RuleDict) -> dict[str, Any]:
    value = rule.get("tags")
    return value if isinstance(value, dict) else {}


def _constraints(rule: RuleDict) -> dict[str, Any]:
    value = rule.get("constraints")
    return value if isinstance(value, dict) else {}


def _same(left: object, right: object) -> bool:
    return str(left).casefold().strip() == str(right).casefold().strip()


def _string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None
