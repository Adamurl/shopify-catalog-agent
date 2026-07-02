from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.writer.write_models import ApprovedPreviewRow

APPROVAL_APPROVED = "APPROVED"
APPROVAL_VALUES = {"PENDING", "APPROVED", "REJECTED", "REVIEW"}


def load_preview_row(
    preview_path: Path,
    product_id: str | None = None,
    row_index: int | None = None,
) -> ApprovedPreviewRow:
    if not preview_path.exists():
        raise ValueError(f"Preview file does not exist: {preview_path}")
    rows = _load_rows(preview_path)
    if product_id and row_index is not None:
        raise ValueError("Use either --product-id or --row-index, not both")
    if product_id:
        matches = [row for row in rows if row.get("product_id") == product_id]
        if len(matches) != 1:
            raise ValueError(
                f"Product ID must appear exactly once in preview; found {len(matches)}"
            )
        raw = matches[0]
        index = rows.index(raw) + 1
        return _parse_row(raw, preview_path, index)
    if row_index is not None:
        if row_index < 1 or row_index > len(rows):
            raise ValueError("--row-index is 1-based and must refer to a preview data row")
        raw = rows[row_index - 1]
        selected_product_id = raw.get("product_id", "")
        matches = [row for row in rows if row.get("product_id") == selected_product_id]
        if len(matches) != 1:
            raise ValueError(
                f"Selected product ID must appear exactly once in preview; found {len(matches)}"
            )
        return _parse_row(raw, preview_path, row_index)
    raise ValueError("Provide --product-id or --row-index")


def find_expected_row(preview_path: Path, product_id: str) -> ApprovedPreviewRow:
    rows = _load_rows(preview_path)
    matches = [row for row in rows if row.get("product_id") == product_id]
    if len(matches) != 1:
        raise ValueError(f"Product ID must appear exactly once in preview; found {len(matches)}")
    return _parse_row(matches[0], preview_path, rows.index(matches[0]) + 1)


def require_approved(row: ApprovedPreviewRow) -> None:
    approval = row.approval.upper()
    if approval not in APPROVAL_VALUES:
        raise ValueError(f"Unknown approval value: {row.approval}")
    if approval != APPROVAL_APPROVED:
        raise ValueError(f"Preview row approval must be APPROVED, got {row.approval}")


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def _parse_row(
    row: dict[str, str],
    preview_path: Path,
    row_index: int,
) -> ApprovedPreviewRow:
    return ApprovedPreviewRow(
        row_index=row_index,
        preview_file=str(preview_path),
        approval=(row.get("approval") or "").strip().upper(),
        product_id=(row.get("product_id") or "").strip(),
        status=(row.get("status") or "").strip(),
        inventory=_parse_int(row.get("inventory")),
        current_title=row.get("current_title", ""),
        suggested_title=row.get("suggested_title", ""),
        current_handle=row.get("current_handle", ""),
        suggested_handle=row.get("suggested_handle", ""),
        current_seo_title=row.get("current_seo_title", ""),
        suggested_seo_title=row.get("suggested_seo_title", ""),
        current_seo_description=row.get("current_seo_description", ""),
        suggested_seo_description=row.get("suggested_seo_description", ""),
        current_description=row.get("current_description", ""),
        suggested_description=row.get("suggested_description", ""),
        current_first_image_alt=row.get("current_first_image_alt", ""),
        suggested_first_image_alt=row.get("suggested_first_image_alt", ""),
        current_tags=_parse_semicolon_values(row.get("current_tags", "")),
        suggested_tags=_parse_semicolon_values(row.get("suggested_tags", "")),
        tags_to_append=_parse_semicolon_values(row.get("tags_to_append", "")),
        detected_family=row.get("detected_family", ""),
        detected_subgroup=row.get("detected_subgroup", ""),
        detected_attributes=_parse_json_object(row.get("detected_attributes", "")),
        confidence=float(row.get("confidence") or 0.0),
        warnings=_parse_semicolon_values(row.get("warnings", "")),
        blocked_fields=_parse_json_list(row.get("blocked_fields", "")),
        rule_id=row.get("rule_id", ""),
        rule_status=row.get("rule_status", ""),
    )


def _parse_semicolon_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _parse_json_list(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return _parse_semicolon_values(value)
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _parse_json_object(value: str) -> dict[str, Any]:
    value = value.strip()
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_int(value: str | None) -> int | None:
    if value is None or not str(value).strip():
        return None
    try:
        return int(float(value))
    except ValueError:
        return None
