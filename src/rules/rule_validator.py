from __future__ import annotations

from src.rules.rule_models import ProposedRule
from src.rules.template_inferer import placeholders

SUPPORTED_PLACEHOLDERS = {
    "title",
    "family",
    "family_slug",
    "design",
    "design_slug",
    "style",
    "size",
    "size_number",
    "color",
    "material",
    "audience",
    "gender",
    "age_group",
    "number_index",
    "set_quantity",
    "accessory_type",
    "use_case",
}


def validate_rule(rule: ProposedRule) -> list[str]:
    warnings: list[str] = []
    if not rule.match.family and not rule.match.subgroup:
        warnings.append("missing_required_match_criteria")
    if not rule.templates.title_pattern:
        warnings.append("missing_title_template")
    if not rule.templates.meta_title_pattern:
        warnings.append("missing_seo_template")

    unsupported = _unsupported_placeholders(rule)
    if unsupported:
        warnings.append(f"unsupported_placeholders:{','.join(sorted(unsupported))}")

    if "handle" in rule.fields.update or rule.constraints.allow_handle_updates:
        warnings.append("handle_update_not_disabled")
    if "description" in rule.fields.update or rule.constraints.allow_description_updates:
        warnings.append("description_update_not_disabled")
    if "image_alt" in rule.fields.update or rule.constraints.allow_image_alt_updates:
        warnings.append("image_alt_update_not_disabled")
    if rule.tags.replace_existing or rule.tags.remove:
        warnings.append("tags_not_append_only")
    if rule.confidence.score < rule.match.min_product_confidence:
        warnings.append("low_confidence_group")
    if rule.product_count < 3:
        warnings.append("small_group")

    missing_placeholder_ratio = _placeholder_missing_ratio(rule)
    if missing_placeholder_ratio > 0.40:
        warnings.append("too_many_placeholders_missing_from_products")

    for example in rule.examples:
        title = example.example_meta_title
        description = example.example_meta_description
        if len(title) > rule.constraints.max_seo_title_length:
            warnings.append("seo_title_likely_too_long")
            break
        if len(description) < rule.constraints.min_meta_description_length:
            warnings.append("meta_description_likely_too_short")
            break
        if len(description) > rule.constraints.max_meta_description_length:
            warnings.append("meta_description_likely_too_long")
            break

    return sorted(set(warnings))


def _unsupported_placeholders(rule: ProposedRule) -> set[str]:
    found: set[str] = set()
    for template in [
        rule.templates.title_pattern,
        rule.templates.handle_pattern,
        rule.templates.meta_title_pattern,
        rule.templates.meta_description_pattern,
        rule.templates.description_template,
        rule.templates.image_alt_template,
    ]:
        found.update(placeholders(template))
    return found - SUPPORTED_PLACEHOLDERS


def _placeholder_missing_ratio(rule: ProposedRule) -> float:
    checked = 0
    missing = 0
    template_placeholders = placeholders(rule.templates.title_pattern) - {"title"}
    for example in rule.examples:
        for placeholder in template_placeholders:
            checked += 1
            value = example.detected_attributes.get(placeholder)
            if not value:
                missing += 1
    return missing / checked if checked else 0.0
