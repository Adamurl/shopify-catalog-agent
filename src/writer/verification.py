from __future__ import annotations

from src.writer.write_models import (
    ApprovedPreviewRow,
    FieldMismatch,
    OneProductUpdate,
    ShopifyProductSnapshot,
)


def verify_snapshot(
    row: ApprovedPreviewRow,
    update: OneProductUpdate,
    after: ShopifyProductSnapshot,
) -> list[FieldMismatch]:
    mismatches: list[FieldMismatch] = []
    if "title" in update.written_fields and after.title != row.suggested_title:
        mismatches.append(FieldMismatch("title", row.suggested_title, after.title))
    if "seo" in update.written_fields:
        if (after.seo_title or "") != row.suggested_seo_title:
            mismatches.append(
                FieldMismatch("seo_title", row.suggested_seo_title, after.seo_title)
            )
        if (after.seo_description or "") != row.suggested_seo_description:
            mismatches.append(
                FieldMismatch(
                    "seo_description",
                    row.suggested_seo_description,
                    after.seo_description,
                )
            )
    if "tags" in update.written_fields and _normalize_tags(after.tags) != _normalize_tags(row.suggested_tags):
        mismatches.append(FieldMismatch("tags", row.suggested_tags, after.tags))
    if "handle" in update.written_fields and after.handle != row.suggested_handle:
        mismatches.append(FieldMismatch("handle", row.suggested_handle, after.handle))
    if "description" in update.written_fields and (after.description_html or "") != row.suggested_description:
        mismatches.append(
            FieldMismatch("description_html", row.suggested_description, after.description_html)
        )
    if "image_alt" in update.written_fields:
        actual_alt = after.media[0].alt_text if after.media else None
        if (actual_alt or "") != row.suggested_first_image_alt:
            mismatches.append(
                FieldMismatch("first_image_alt", row.suggested_first_image_alt, actual_alt)
            )
    return mismatches


def expected_written_values(
    row: ApprovedPreviewRow,
    update: OneProductUpdate,
) -> dict[str, object]:
    expected: dict[str, object] = {}
    if "title" in update.written_fields:
        expected["title"] = row.suggested_title
    if "seo" in update.written_fields:
        expected["seo_title"] = row.suggested_seo_title
        expected["seo_description"] = row.suggested_seo_description
    if "tags" in update.written_fields:
        expected["tags"] = row.suggested_tags
    if "handle" in update.written_fields:
        expected["handle"] = row.suggested_handle
    if "description" in update.written_fields:
        expected["description_html"] = row.suggested_description
    if "image_alt" in update.written_fields:
        expected["first_image_alt"] = row.suggested_first_image_alt
    return expected


def _normalize_tags(tags: list[str]) -> set[str]:
    return {" ".join(tag.casefold().split()) for tag in tags if tag.strip()}
