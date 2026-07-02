from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.catalog.utils import ensure_directory, write_json
from src.preview.preview_models import PreviewDocument, PreviewRow

PREVIEW_COLUMNS = [
    "approval",
    "product_id",
    "status",
    "inventory",
    "current_title",
    "suggested_title",
    "current_handle",
    "suggested_handle",
    "current_seo_title",
    "suggested_seo_title",
    "current_seo_description",
    "suggested_seo_description",
    "current_description",
    "suggested_description",
    "current_first_image_alt",
    "suggested_first_image_alt",
    "current_tags",
    "suggested_tags",
    "tags_to_append",
    "detected_family",
    "detected_subgroup",
    "detected_attributes",
    "confidence",
    "warnings",
    "blocked_fields",
    "rule_id",
    "rule_status",
]

WARNING_COLUMNS = [
    "rule_id",
    "group",
    "product_id",
    "title",
    "warnings",
    "blocked_fields",
    "suggested_fix",
]


def write_preview_outputs(
    previews: list[PreviewDocument],
    previews_dir: Path,
    reports_dir: Path,
    timestamp: str,
) -> dict[str, Path]:
    ensure_directory(previews_dir)
    ensure_directory(reports_dir)
    paths: dict[str, Path] = {}
    for preview in previews:
        safe_group = preview.preview_id.removesuffix(f"_{timestamp}")
        csv_path = previews_dir / f"preview_{safe_group}_{timestamp}.csv"
        json_path = previews_dir / f"preview_{safe_group}_{timestamp}.json"
        summary_path = reports_dir / f"preview_summary_{safe_group}_{timestamp}.md"
        warnings_path = reports_dir / f"preview_warnings_{safe_group}_{timestamp}.csv"

        _write_csv(csv_path, PREVIEW_COLUMNS, [_row_to_csv(row) for row in preview.rows])
        write_json(json_path, preview.to_dict())
        summary_path.write_text(render_preview_summary(preview), encoding="utf-8")
        _write_csv(warnings_path, WARNING_COLUMNS, _warning_rows(preview))

        paths[f"{preview.rule_id}:csv"] = csv_path
        paths[f"{preview.rule_id}:json"] = json_path
        paths[f"{preview.rule_id}:summary"] = summary_path
        paths[f"{preview.rule_id}:warnings"] = warnings_path
    return paths


def render_preview_summary(preview: PreviewDocument) -> str:
    rows_with_warnings = [row for row in preview.rows if row.warnings]
    rows_with_blocked = [row for row in preview.rows if row.blocked_fields]
    rows_blocked_or_warned = [
        row for row in preview.rows if row.warnings or row.blocked_fields
    ]
    safe_changes = [
        row
        for row in preview.rows
        if not row.warnings and _has_safe_change(row)
    ]
    warnings = Counter(warning for row in preview.rows for warning in row.warnings)
    lines = [
        "# Preview Summary",
        "",
        "READ ONLY MODE: no Shopify data was changed.",
        "",
        f"Preview group/rule: {preview.group} / {preview.rule_id}",
        f"Rule status: {preview.rule_status}",
        "",
        "## Counts",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Matched products | {preview.products_count} |",
        f"| Products with safe changes | {len(safe_changes)} |",
        f"| Products needing manual review | {len(rows_with_warnings)} |",
        f"| Products blocked because of warnings/fields | {len(rows_blocked_or_warned)} |",
        "",
        "## Fields Included In Preview",
        "",
        "- title",
        "- seo_title",
        "- seo_description",
        "- tags",
        "- handle",
        "- description",
        "- image_alt",
        "",
        "## Fields Blocked By Default",
        "",
        "- handle",
        "- description",
        "- image_alt",
        "",
        "## Top Warnings",
        "",
    ]
    if warnings:
        lines.extend(f"- {warning}: {count}" for warning, count in warnings.most_common(20))
    else:
        lines.append("- None")
    lines.extend(["", "## Example Before/After Rows", ""])
    for row in preview.rows[:5]:
        lines.append(f"- {row.product_id}: `{row.current.title}` -> `{row.suggested.title}`")
    if not preview.rows:
        lines.append("- No products matched this rule.")
    lines.extend(
        [
            "",
            "## Safety Reminder",
            "",
            "This preview is for human review only. No Shopify data was changed.",
            "",
        ]
    )
    return "\n".join(lines)


def _row_to_csv(row: PreviewRow) -> dict[str, Any]:
    return {
        "approval": row.approval,
        "product_id": row.product_id,
        "status": row.status,
        "inventory": row.inventory,
        "current_title": row.current.title,
        "suggested_title": row.suggested.title,
        "current_handle": row.current.handle,
        "suggested_handle": row.suggested.handle,
        "current_seo_title": row.current.seo_title,
        "suggested_seo_title": row.suggested.seo_title,
        "current_seo_description": row.current.seo_description,
        "suggested_seo_description": row.suggested.seo_description,
        "current_description": row.current.description_html,
        "suggested_description": row.suggested.description_html,
        "current_first_image_alt": row.current.first_image_alt,
        "suggested_first_image_alt": row.suggested.first_image_alt,
        "current_tags": "; ".join(row.current.tags),
        "suggested_tags": "; ".join(row.suggested.tags),
        "tags_to_append": "; ".join(row.tags_to_append),
        "detected_family": row.detected_family or "",
        "detected_subgroup": row.detected_subgroup or "",
        "detected_attributes": json.dumps(row.detected_attributes, ensure_ascii=False, sort_keys=True),
        "confidence": f"{row.confidence:.2f}",
        "warnings": "; ".join(row.warnings),
        "blocked_fields": json.dumps(row.blocked_fields),
        "rule_id": row.rule_id,
        "rule_status": row.rule_status,
    }


def _warning_rows(preview: PreviewDocument) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in preview.rows:
        if not row.warnings and not row.blocked_fields:
            continue
        rows.append(
            {
                "rule_id": preview.rule_id,
                "group": preview.group,
                "product_id": row.product_id,
                "title": row.current.title,
                "warnings": "; ".join(row.warnings),
                "blocked_fields": "; ".join(row.blocked_fields),
                "suggested_fix": _suggested_fix(row),
            }
        )
    return rows


def _suggested_fix(row: PreviewRow) -> str:
    if "missing_required_attribute" in row.warnings:
        return "Fix classification attributes or narrow the rule match criteria."
    if "duplicate_suggested_handle" in row.warnings:
        return "Edit handle template or keep handle blocked."
    if "rule_status_is_proposed_not_approved" in row.warnings:
        return "Human-review and approve the rule before applying in a later phase."
    if row.blocked_fields:
        return "Blocked fields should remain unchanged unless the rule is explicitly approved for them."
    return "Review this row before approval."


def _has_safe_change(row: PreviewRow) -> bool:
    return (
        row.current.title != row.suggested.title
        or row.current.seo_title != row.suggested.seo_title
        or row.current.seo_description != row.suggested.seo_description
        or bool(row.tags_to_append)
    )


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
