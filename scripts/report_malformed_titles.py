from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audits.title_audit import TitleAuditFinding, audit_titles
from src.shopify.snapshot import load_products_from_snapshot

DEFAULT_INPUT_PATH = Path("data/raw/products.json")
DEFAULT_CSV_PATH = Path("data/reports/malformed_titles.csv")
DEFAULT_MARKDOWN_PATH = Path("data/reports/malformed_titles.md")
DEFAULT_EXCLUDED_ISSUES = {"Missing product type"}


@dataclass(frozen=True)
class TitleReportRow:
    product_id: str
    title: str
    issues: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report products with malformed or inconsistent titles."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Product snapshot JSON path.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="CSV report output path.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=DEFAULT_MARKDOWN_PATH,
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of product rows to print in the terminal.",
    )
    parser.add_argument(
        "--include-product-type",
        action="store_true",
        help="Include missing product type findings in the report.",
    )
    return parser.parse_args()


def build_title_report_rows(findings: list[TitleAuditFinding]) -> list[TitleReportRow]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for finding in findings:
        key = (finding.product_id, finding.title)
        grouped.setdefault(key, []).append(finding.issue)

    return [
        TitleReportRow(product_id=product_id, title=title, issues=sorted(set(issues)))
        for (product_id, title), issues in sorted(
            grouped.items(), key=lambda item: item[0][1]
        )
    ]


def write_title_report_csv(rows: list[TitleReportRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["product_id", "title", "issues"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "product_id": row.product_id,
                    "title": row.title,
                    "issues": "; ".join(row.issues),
                }
            )


def render_title_report_markdown(rows: list[TitleReportRow]) -> str:
    lines = [
        "# Malformed Product Titles",
        "",
        f"Products with title findings: {len(rows)}",
        "",
        "| Title | Issues |",
        "| --- | --- |",
    ]
    for row in rows:
        title = _escape_markdown_table(row.title)
        issues = _escape_markdown_table("; ".join(row.issues))
        lines.append(f"| {title} | {issues} |")
    return "\n".join(lines) + "\n"


def write_title_report_markdown(rows: list[TitleReportRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_title_report_markdown(rows), encoding="utf-8")


def main() -> int:
    args = parse_args()

    try:
        products = load_products_from_snapshot(args.input)
        findings = audit_titles(products)
        report_findings = _filter_report_findings(
            findings,
            include_product_type=args.include_product_type,
        )
        rows = build_title_report_rows(report_findings)
        write_title_report_csv(rows, args.csv)
        write_title_report_markdown(rows, args.markdown)
    except Exception as exc:
        print(f"Malformed title report failed: {exc}")
        return 1

    issue_counts = Counter(finding.issue for finding in report_findings)
    print("Malformed title report complete")
    print(f"Products scanned: {len(products)}")
    print(f"Products with title findings: {len(rows)}")
    print(f"Total title findings: {len(report_findings)}")
    print(f"CSV report: {args.csv}")
    print(f"Markdown report: {args.markdown}")
    print("")
    print("Issue counts:")
    for issue, count in sorted(issue_counts.items()):
        print(f"- {issue}: {count}")

    if args.limit > 0 and rows:
        print("")
        print(f"First {min(args.limit, len(rows))} products:")
        for row in rows[: args.limit]:
            print(f"- {row.title}: {'; '.join(row.issues)}")

    return 0


def _escape_markdown_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _filter_report_findings(
    findings: list[TitleAuditFinding],
    include_product_type: bool,
) -> list[TitleAuditFinding]:
    if include_product_type:
        return findings
    return [
        finding for finding in findings if finding.issue not in DEFAULT_EXCLUDED_ISSUES
    ]


if __name__ == "__main__":
    raise SystemExit(main())
