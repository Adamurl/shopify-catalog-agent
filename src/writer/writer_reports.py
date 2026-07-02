from __future__ import annotations

from pathlib import Path

from src.catalog.utils import ensure_directory, write_json
from src.writer.write_models import VerificationResult


def write_verification_reports(
    result: VerificationResult,
    reports_dir: Path,
    timestamp: str,
) -> dict[str, Path]:
    ensure_directory(reports_dir)
    paths = {
        "verification_md": reports_dir / f"one_product_verification_{timestamp}.md",
        "verification_json": reports_dir / f"one_product_verification_{timestamp}.json",
    }
    paths["verification_md"].write_text(render_verification_markdown(result), encoding="utf-8")
    write_json(paths["verification_json"], result.to_dict())
    return paths


def render_verification_markdown(result: VerificationResult) -> str:
    lines = [
        "# One Product Verification",
        "",
        f"Mode: {result.mode}",
        f"Product ID: {result.product_id}",
        f"Preview file: {result.preview_file}",
        f"Write attempted: {result.write_attempted}",
        f"Verification passed: {result.verification_passed}",
        "",
        "## Written Fields",
        "",
    ]
    lines.extend(f"- {field}" for field in result.written_fields)
    if not result.written_fields:
        lines.append("- None")
    lines.extend(["", "## Blocked Fields", ""])
    lines.extend(f"- {field}" for field in result.blocked_fields)
    if not result.blocked_fields:
        lines.append("- None")
    lines.extend(["", "## Mismatches", ""])
    if result.mismatches:
        for mismatch in result.mismatches:
            lines.append(
                f"- {mismatch.field}: expected `{mismatch.expected}`, got `{mismatch.actual}`"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Safety Note",
            "",
            "This command is a one-product test update only. Bulk updates are not implemented.",
            "",
        ]
    )
    return "\n".join(lines)
