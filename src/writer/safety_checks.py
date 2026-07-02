from __future__ import annotations

import re

from src.writer.write_models import ApprovedPreviewRow, OneProductUpdate

SHOPIFY_PRODUCT_GID_RE = re.compile(r"^gid://shopify/Product/\d+$")
DEFAULT_SAFE_FIELDS = ["title", "seo", "tags"]
OPTIONAL_RISKY_FIELDS = ["handle", "description", "image_alt"]


def validate_row_for_apply(row: ApprovedPreviewRow) -> list[str]:
    warnings: list[str] = []
    if not SHOPIFY_PRODUCT_GID_RE.match(row.product_id):
        raise ValueError(f"Invalid Shopify product GID: {row.product_id}")
    if not row.rule_id:
        raise ValueError("Preview row is missing rule_id")
    if row.status != "ACTIVE":
        raise ValueError(f"Refusing inactive product by default: {row.status}")
    if not row.suggested_title:
        raise ValueError("Suggested title is empty")
    if not row.suggested_seo_title:
        raise ValueError("Suggested SEO title is empty")
    if not row.suggested_seo_description:
        raise ValueError("Suggested SEO description is empty")
    if len(row.suggested_seo_title) > 60:
        raise ValueError("Suggested SEO title is too long")
    if len(row.suggested_seo_description) > 160:
        raise ValueError("Suggested SEO description is too long")
    if not _tags_append_only(row):
        raise ValueError("Suggested tags must preserve existing tags and append only")
    if "shared_media_image_id_across_multiple_products" in row.warnings and _image_alt_would_change(row):
        raise ValueError("Refusing image alt update for shared media")
    if "handle" in row.blocked_fields and _handle_would_change(row):
        warnings.append("handle blocked and will not be written")
    if "description" in row.blocked_fields and _description_would_change(row):
        warnings.append("description blocked and will not be written")
    if "image_alt" in row.blocked_fields and _image_alt_would_change(row):
        warnings.append("image_alt blocked and will not be written")
    return warnings


def build_update_from_row(row: ApprovedPreviewRow) -> OneProductUpdate:
    written_fields: list[str] = []
    update = {
        "product_id": row.product_id,
        "written_fields": written_fields,
        "title": None,
        "seo_title": None,
        "seo_description": None,
        "tags": None,
        "description_html": None,
        "handle": None,
        "first_image_alt": None,
    }

    if row.suggested_title and row.suggested_title != row.current_title:
        update["title"] = row.suggested_title
        written_fields.append("title")
    if (
        row.suggested_seo_title
        and row.suggested_seo_description
        and (
            row.suggested_seo_title != row.current_seo_title
            or row.suggested_seo_description != row.current_seo_description
        )
    ):
        update["seo_title"] = row.suggested_seo_title
        update["seo_description"] = row.suggested_seo_description
        written_fields.append("seo")
    if row.tags_to_append:
        update["tags"] = _dedupe_tags(row.suggested_tags)
        written_fields.append("tags")

    if "handle" not in row.blocked_fields and _handle_would_change(row):
        update["handle"] = row.suggested_handle
        written_fields.append("handle")
    if "description" not in row.blocked_fields and _description_would_change(row):
        update["description_html"] = row.suggested_description
        written_fields.append("description")
    if "image_alt" not in row.blocked_fields and _image_alt_would_change(row):
        update["first_image_alt"] = row.suggested_first_image_alt
        written_fields.append("image_alt")

    if not written_fields:
        raise ValueError("No fields would be written for this approved row")
    return OneProductUpdate(**update)


def _tags_append_only(row: ApprovedPreviewRow) -> bool:
    suggested = {_normalize_tag(tag) for tag in row.suggested_tags}
    return all(_normalize_tag(tag) in suggested for tag in row.current_tags)


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        key = _normalize_tag(tag)
        if key and key not in seen:
            result.append(tag)
            seen.add(key)
    return result


def _normalize_tag(tag: str) -> str:
    return " ".join(tag.casefold().split())


def _handle_would_change(row: ApprovedPreviewRow) -> bool:
    return bool(row.suggested_handle and row.suggested_handle != row.current_handle)


def _description_would_change(row: ApprovedPreviewRow) -> bool:
    return bool(row.suggested_description and row.suggested_description != row.current_description)


def _image_alt_would_change(row: ApprovedPreviewRow) -> bool:
    return bool(
        row.suggested_first_image_alt
        and row.suggested_first_image_alt != row.current_first_image_alt
    )
