from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.preview.preview_models import PreviewDocument
from src.preview.preview_validator import validate_preview_rows
from src.preview.rule_renderer import load_rule, product_matches_rule, render_preview_row
from src.rules.rule_utils import safe_group_name


def find_rule_paths(
    proposed_dir: Path,
    approved_dir: Path,
    explicit_rule: Path | None = None,
    approved_rules_only: bool = False,
) -> list[Path]:
    if explicit_rule:
        return [explicit_rule]
    directories = [approved_dir] if approved_rules_only else [proposed_dir, approved_dir]
    paths: list[Path] = []
    for directory in directories:
        if directory.exists():
            paths.extend(sorted(directory.glob("*.json")))
    return paths


def build_previews(
    products: list[dict[str, Any]],
    rule_paths: list[Path],
    timestamp: str,
) -> list[PreviewDocument]:
    previews: list[PreviewDocument] = []
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for path in rule_paths:
        rule = load_rule(path)
        matched = [product for product in products if product_matches_rule(product, rule)]
        rows = [render_preview_row(product, rule) for product in matched]
        rows = validate_preview_rows(rows, matched, rule)
        group = str(rule.get("group") or rule.get("rule_id") or path.stem)
        preview_id = f"{safe_group_name(group)}_{timestamp}"
        previews.append(
            PreviewDocument(
                preview_id=preview_id,
                created_at=created_at,
                mode="READ_ONLY",
                rule_id=str(rule.get("rule_id") or ""),
                rule_status=str(rule.get("status") or ""),
                group=group,
                products_count=len(rows),
                rows=rows,
            )
        )
    return previews
