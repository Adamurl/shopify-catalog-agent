from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.catalog.utils import ensure_directory
from src.rules.rule_models import ProposedRule

PROPOSED_RULE_COLUMNS = [
    "rule_id",
    "group",
    "family",
    "subgroup",
    "product_count",
    "confidence",
    "update_fields",
    "leave_alone_fields",
    "title_pattern",
    "meta_title_pattern",
    "meta_description_pattern",
    "append_tags",
    "warnings",
    "rule_path",
]

MANUAL_REVIEW_COLUMNS = [
    "rule_id",
    "group",
    "reason",
    "warnings",
    "suggested_fix",
    "affected_products",
    "rule_path",
]


def write_rule_reports(
    rules: list[ProposedRule],
    rule_paths: dict[str, Path],
    reports_dir: Path,
    timestamp: str,
    filter_label: str,
) -> dict[str, Path]:
    ensure_directory(reports_dir)
    paths = {
        "rule_proposal_summary": reports_dir / f"rule_proposal_summary_{timestamp}.md",
        "proposed_rules": reports_dir / f"proposed_rules_{timestamp}.csv",
        "rule_manual_review": reports_dir / f"rule_manual_review_{timestamp}.csv",
    }
    paths["rule_proposal_summary"].write_text(
        render_rule_summary(rules, filter_label),
        encoding="utf-8",
    )
    _write_csv(paths["proposed_rules"], PROPOSED_RULE_COLUMNS, _proposed_rule_rows(rules, rule_paths))
    _write_csv(paths["rule_manual_review"], MANUAL_REVIEW_COLUMNS, _manual_review_rows(rules, rule_paths))
    return paths


def render_rule_summary(rules: list[ProposedRule], filter_label: str) -> str:
    manual_review = [rule for rule in rules if rule.confidence.warnings]
    families = sorted({rule.family for rule in rules if rule.family})
    subgroups = sorted({rule.subgroup for rule in rules if rule.subgroup})
    lines = [
        "# Rule Proposal Summary",
        "",
        "READ ONLY MODE: proposed rules were saved locally only. No Shopify data was changed.",
        "",
        f"Scope: {filter_label}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total proposed rules | {len(rules)} |",
        f"| Families covered | {len(families)} |",
        f"| Subgroups covered | {len(subgroups)} |",
        f"| Rules needing manual review | {len(manual_review)} |",
        "",
        "## Families Covered",
        "",
    ]
    lines.extend([f"- {family}" for family in families] or ["- None"])
    lines.extend(["", "## Subgroups Covered", ""])
    lines.extend([f"- {subgroup}" for subgroup in subgroups] or ["- None"])
    lines.extend(
        [
            "",
            "## Risky Fields Disabled By Default",
            "",
            "- Handles are in `leave_alone` and `allow_handle_updates` is false.",
            "- Descriptions are in `leave_alone` and `allow_description_updates` is false.",
            "- Image alt text is in `leave_alone` and `allow_image_alt_updates` is false.",
            "- Tags are append-only by default.",
            "",
            "## Rules Needing Manual Review",
            "",
        ]
    )
    if manual_review:
        for rule in manual_review:
            lines.append(f"- {rule.rule_id}: {', '.join(rule.confidence.warnings)}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            "Human edit and approve proposed JSON rules before Phase 4 preview generation.",
            "",
            "## Safety Notes",
            "",
            "- Rules are proposals only.",
            "- No preview/apply flow was run.",
            "- No AI/LLM-generated product copy was created.",
            "- No Shopify mutations or writers were called.",
            "",
        ]
    )
    return "\n".join(lines)


def _proposed_rule_rows(
    rules: list[ProposedRule],
    rule_paths: dict[str, Path],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule in rules:
        rows.append(
            {
                "rule_id": rule.rule_id,
                "group": rule.group,
                "family": rule.family or "",
                "subgroup": rule.subgroup or "",
                "product_count": rule.product_count,
                "confidence": f"{rule.confidence.score:.2f}",
                "update_fields": "; ".join(rule.fields.update),
                "leave_alone_fields": "; ".join(rule.fields.leave_alone),
                "title_pattern": rule.templates.title_pattern,
                "meta_title_pattern": rule.templates.meta_title_pattern,
                "meta_description_pattern": rule.templates.meta_description_pattern,
                "append_tags": "; ".join(rule.tags.append),
                "warnings": "; ".join(rule.confidence.warnings),
                "rule_path": str(rule_paths.get(rule.rule_id, "")),
            }
        )
    return rows


def _manual_review_rows(
    rules: list[ProposedRule],
    rule_paths: dict[str, Path],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.confidence.warnings:
            continue
        rows.append(
            {
                "rule_id": rule.rule_id,
                "group": rule.group,
                "reason": "; ".join(rule.confidence.warnings),
                "warnings": "; ".join(rule.confidence.warnings),
                "suggested_fix": _suggested_fix(rule.confidence.warnings),
                "affected_products": "; ".join(rule.source_product_ids[:20]),
                "rule_path": str(rule_paths.get(rule.rule_id, "")),
            }
        )
    return rows


def _suggested_fix(warnings: list[str]) -> str:
    if "small_group" in warnings:
        return "Review examples and approve only if this group should have its own rule."
    if "too_many_placeholders_missing_from_products" in warnings:
        return "Remove placeholders that are missing from many products or improve classification attributes."
    if "meta_description_likely_too_short" in warnings or "meta_description_likely_too_long" in warnings:
        return "Edit meta description template to fit the configured length range."
    if "accessory_main_product_mixed" in warnings:
        return "Split accessory and main product rules."
    return "Human review required before approval."


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
