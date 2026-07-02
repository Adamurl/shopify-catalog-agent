from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from src.preview.diff_utils import important_words_removed
from src.preview.preview_models import PreviewRow
from src.rules.rule_validator import SUPPORTED_PLACEHOLDERS
from src.rules.template_inferer import placeholders


def validate_preview_rows(
    rows: list[PreviewRow],
    products: list[dict[str, Any]],
    rule: dict[str, Any],
) -> list[PreviewRow]:
    handle_counts = Counter(row.suggested.handle for row in rows if row.suggested.handle)
    shared_media_ids = _shared_media_ids(products)
    rule_warnings = _rule_warnings(rule)
    validated: list[PreviewRow] = []
    for row in rows:
        product = next((item for item in products if str(item.get("id")) == row.product_id), {})
        warnings = [
            *row.warnings,
            *rule_warnings,
            *_row_warnings(row, product, rule, handle_counts, shared_media_ids),
        ]
        validated.append(replace(row, warnings=sorted(set(warnings))))
    return validated


def _row_warnings(
    row: PreviewRow,
    product: dict[str, Any],
    rule: dict[str, Any],
    handle_counts: Counter[str],
    shared_media_ids: set[str],
) -> list[str]:
    warnings: list[str] = []
    constraints = _constraints(rule)
    classification = _classification(product)

    if row.suggested.handle and handle_counts[row.suggested.handle] > 1:
        warnings.append("duplicate_suggested_handle")
    if row.suggested.handle != row.current.handle:
        warnings.append("suggested_handle_differs_from_current_handle")
        warnings.append("current_handle_may_have_backlinks")
        if not constraints.get("allow_handle_updates", False):
            warnings.append("handle_updates_disabled")
    if len(row.suggested.seo_title) > int(constraints.get("max_seo_title_length") or 60):
        warnings.append("seo_title_too_long")
    min_desc = int(constraints.get("min_meta_description_length") or 120)
    max_desc = int(constraints.get("max_meta_description_length") or 160)
    if not row.suggested.seo_title or not row.suggested.seo_description:
        warnings.append("suggested_seo_values_are_empty")
    if len(row.suggested.seo_description) < min_desc:
        warnings.append("seo_description_too_short")
    if len(row.suggested.seo_description) > max_desc:
        warnings.append("seo_description_too_long")
    if not _has_required_attributes(row, rule):
        warnings.append("missing_required_attribute")
    if row.confidence < float(_match(rule).get("min_product_confidence") or 0.0):
        warnings.append("low_confidence_product")
    if float((_confidence(rule).get("score") or 0.0)) < float(_match(rule).get("min_product_confidence") or 0.0):
        warnings.append("low_confidence_rule")
    if not _images(product):
        warnings.append("missing_image")
    if _images(product) and not row.current.first_image_alt:
        warnings.append("missing_first_image_alt")
    if any(image.get("id") in shared_media_ids for image in _images(product)):
        warnings.append("shared_media_image_id_across_multiple_products")
    if len(product.get("variants", []) or []) > 1:
        warnings.append("product_has_variants_that_may_need_different_naming")
    if row.status != "ACTIVE":
        warnings.append("inactive_product")
    if row.status in {"DRAFT", "ARCHIVED"}:
        warnings.append("product_is_draft_or_archived")
    if row.inventory is not None and row.inventory <= 0:
        warnings.append("product_has_no_inventory")
    if classification.get("is_accessory") and (_match(rule).get("exclude_if") or {}).get("is_accessory") is True:
        warnings.append("product_appears_to_be_accessory_but_rule_is_for_main_product")
    if classification.get("conflicting_signals"):
        warnings.append("product_belongs_to_multiple_competing_groups")
    if important_words_removed(row.current.title, row.suggested.title):
        warnings.append("suggested_title_removes_important_current_words")
    if row.suggested.title == row.current.title:
        warnings.append("suggested_title_equals_current_title")
    if _description_too_generic(row.suggested.description_html):
        warnings.append("suggested_description_too_generic")
    if row.rule_status == "proposed":
        warnings.append("rule_status_is_proposed_not_approved")
    if "handle" in row.blocked_fields:
        warnings.append("handle_updates_disabled")
    if "description" in row.blocked_fields:
        warnings.append("description_updates_disabled")
    if "image_alt" in row.blocked_fields:
        warnings.append("image_alt_updates_disabled")
    return warnings


def _rule_warnings(rule: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    found: set[str] = set()
    for template in (_templates(rule).values()):
        if isinstance(template, str):
            found.update(placeholders(template))
    unsupported = found - SUPPORTED_PLACEHOLDERS
    if unsupported:
        warnings.append("unsupported_placeholder_in_rule")
    if rule.get("status") == "proposed":
        warnings.append("rule_status_is_proposed_not_approved")
    return warnings


def _has_required_attributes(row: PreviewRow, rule: dict[str, Any]) -> bool:
    for name, expected in (_match(rule).get("required_attributes") or {}).items():
        value = row.detected_attributes.get(name)
        if str(value).casefold().strip() != str(expected).casefold().strip():
            return False
    return True


def _shared_media_ids(products: list[dict[str, Any]]) -> set[str]:
    counter: Counter[str] = Counter()
    for product in products:
        for image in _images(product):
            image_id = image.get("id")
            if image_id:
                counter[str(image_id)] += 1
    return {image_id for image_id, count in counter.items() if count > 1}


def _description_too_generic(value: str) -> bool:
    text = " ".join(value.split()).casefold()
    return text in {
        "",
        "product image.",
        "review this placeholder before approval.",
    } or "placeholder" in text


def _images(product: dict[str, Any]) -> list[dict[str, Any]]:
    images = product.get("images")
    return [image for image in images if isinstance(image, dict)] if isinstance(images, list) else []


def _classification(product: dict[str, Any]) -> dict[str, Any]:
    value = product.get("classification")
    return value if isinstance(value, dict) else {}


def _match(rule: dict[str, Any]) -> dict[str, Any]:
    value = rule.get("match")
    return value if isinstance(value, dict) else {}


def _templates(rule: dict[str, Any]) -> dict[str, Any]:
    value = rule.get("templates")
    return value if isinstance(value, dict) else {}


def _constraints(rule: dict[str, Any]) -> dict[str, Any]:
    value = rule.get("constraints")
    return value if isinstance(value, dict) else {}


def _confidence(rule: dict[str, Any]) -> dict[str, Any]:
    value = rule.get("confidence")
    return value if isinstance(value, dict) else {}
