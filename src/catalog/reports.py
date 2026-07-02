from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from src.catalog.analyzer import CatalogAnalysis, GroupAnalysis, ProductIssue
from src.catalog.models import CatalogProduct
from src.catalog.utils import ensure_directory

PRODUCT_ISSUE_COLUMNS = [
    "product_id",
    "title",
    "handle",
    "status",
    "product_type",
    "vendor",
    "collections",
    "tags",
    "total_inventory",
    "issue_type",
    "details",
]

GROUP_COLUMNS = [
    "group_type",
    "group_name",
    "product_count",
    "active_count",
    "in_stock_count",
    "missing_seo_title_count",
    "missing_seo_description_count",
    "missing_image_alt_count",
    "duplicate_title_count",
    "duplicate_handle_count",
    "weak_description_count",
    "unique_title_patterns",
    "may_be_too_broad",
    "details",
]

TITLE_PATTERN_COLUMNS = ["pattern_type", "pattern", "count"]


def write_reports(
    analysis: CatalogAnalysis,
    output_dir: Path,
    timestamp: str,
    filter_label: str = "ACTIVE products",
) -> dict[str, Path]:
    """Write all Phase 1 report files and return their paths."""
    ensure_directory(output_dir)
    paths = {
        "catalog_summary": output_dir / f"catalog_summary_{timestamp}.md",
        "group_summary": output_dir / f"group_summary_{timestamp}.csv",
        "missing_seo": output_dir / f"missing_seo_{timestamp}.csv",
        "missing_image_alt": output_dir / f"missing_image_alt_{timestamp}.csv",
        "duplicate_titles": output_dir / f"duplicate_titles_{timestamp}.csv",
        "duplicate_handles": output_dir / f"duplicate_handles_{timestamp}.csv",
        "weak_descriptions": output_dir / f"weak_descriptions_{timestamp}.csv",
        "title_patterns": output_dir / f"title_patterns_{timestamp}.csv",
        "broad_groups": output_dir / f"broad_groups_{timestamp}.csv",
    }

    paths["catalog_summary"].write_text(
        render_markdown_summary(analysis, filter_label),
        encoding="utf-8",
    )
    write_group_summary_csv(analysis.group_analyses, paths["group_summary"])
    write_issue_csv(
        [*analysis.missing_seo_title, *analysis.missing_seo_description],
        paths["missing_seo"],
    )
    write_issue_csv(
        [*analysis.missing_first_image_alt, *analysis.no_images],
        paths["missing_image_alt"],
    )
    write_issue_csv(analysis.duplicate_titles, paths["duplicate_titles"])
    write_issue_csv(analysis.duplicate_handles, paths["duplicate_handles"])
    write_issue_csv(analysis.weak_descriptions, paths["weak_descriptions"])
    write_title_patterns_csv(analysis, paths["title_patterns"])
    write_group_summary_csv(analysis.broad_groups, paths["broad_groups"])
    return paths


def render_markdown_summary(analysis: CatalogAnalysis, filter_label: str) -> str:
    lines = [
        "# Catalog SEO Audit Summary",
        "",
        "READ ONLY MODE: no Shopify data was changed.",
        "",
        f"Scope: {filter_label}",
        "",
        "## Overall Catalog Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total products analyzed | {analysis.total_products} |",
        f"| Active products | {analysis.active_products} |",
        f"| In-stock products | {analysis.in_stock_products} |",
        f"| Missing SEO title | {len(analysis.missing_seo_title)} |",
        f"| Missing SEO description | {len(analysis.missing_seo_description)} |",
        f"| Missing first image alt text | {len(analysis.missing_first_image_alt)} |",
        f"| Products with no images | {len(analysis.no_images)} |",
        f"| Duplicate title rows | {len(analysis.duplicate_titles)} |",
        f"| Duplicate handle rows | {len(analysis.duplicate_handles)} |",
        f"| Weak descriptions | {len(analysis.weak_descriptions)} |",
        f"| Missing product type | {len(analysis.missing_product_type)} |",
        f"| Missing tags | {len(analysis.missing_tags)} |",
        "",
        "## Top Issues",
        "",
    ]
    issue_counts = [
        ("Missing SEO title", len(analysis.missing_seo_title)),
        ("Missing SEO description", len(analysis.missing_seo_description)),
        ("Missing first image alt text", len(analysis.missing_first_image_alt)),
        ("Products with no images", len(analysis.no_images)),
        ("Weak descriptions", len(analysis.weak_descriptions)),
        ("Duplicate titles", len(analysis.duplicate_titles)),
        ("Duplicate handles", len(analysis.duplicate_handles)),
    ]
    for name, count in sorted(issue_counts, key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Product Type Summary", ""])
    lines.extend(_group_table(analysis.group_analyses, "product_type"))
    lines.extend(["", "## Collection Summary", ""])
    lines.extend(_group_table(analysis.group_analyses, "collection"))
    lines.extend(["", "## Tag Summary", ""])
    lines.extend(_group_table(analysis.group_analyses, "tag"))
    lines.extend(["", "## Broad Group Warnings", ""])
    if analysis.broad_groups:
        for group in analysis.broad_groups[:25]:
            details = "; ".join(group.broad_reasons)
            lines.append(
                f"- {group.group_type}: {group.group_name} "
                f"({group.product_count} products) - {details}"
            )
    else:
        lines.append("- No broad group warnings found.")

    lines.extend(["", "## Recommended Next Categories To Clean First", ""])
    recommendations = _recommended_groups(analysis.group_analyses)
    if recommendations:
        for group in recommendations:
            lines.append(
                f"- {group.group_type}: {group.group_name} "
                f"({group.product_count} products, "
                f"{_group_issue_count(group)} issue signals)"
            )
    else:
        lines.append("- No high-priority groups found in this scope.")

    lines.extend(
        [
            "",
            "## Title Pattern Signals",
            "",
            "### Common Prefixes",
            "",
        ]
    )
    lines.extend(_counter_lines(analysis.common_title_prefixes))
    lines.extend(["", "### Common Suffixes", ""])
    lines.extend(_counter_lines(analysis.common_title_suffixes))
    lines.extend(["", "### Common Repeated Words", ""])
    lines.extend(_counter_lines(analysis.common_repeated_words))

    lines.extend(
        [
            "",
            "## Safety Notes",
            "",
            "- This report is deterministic and read-only.",
            "- The Phase 1 CLI does not call Shopify mutations.",
            "- No AI-generated product copy, SEO copy, tags, handles, descriptions, or image alt text were created.",
            "",
        ]
    )
    return "\n".join(lines)


def write_issue_csv(issues: Iterable[ProductIssue], output_path: Path) -> None:
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PRODUCT_ISSUE_COLUMNS)
        writer.writeheader()
        for issue in issues:
            writer.writerow(_issue_row(issue))


def write_group_summary_csv(groups: Iterable[GroupAnalysis], output_path: Path) -> None:
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=GROUP_COLUMNS)
        writer.writeheader()
        for group in groups:
            writer.writerow(_group_row(group))


def write_title_patterns_csv(analysis: CatalogAnalysis, output_path: Path) -> None:
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TITLE_PATTERN_COLUMNS)
        writer.writeheader()
        for pattern, count in analysis.title_patterns.items():
            writer.writerow(
                {"pattern_type": "title_pattern", "pattern": pattern, "count": count}
            )
        for pattern, count in analysis.common_title_prefixes.items():
            writer.writerow(
                {"pattern_type": "common_prefix", "pattern": pattern, "count": count}
            )
        for pattern, count in analysis.common_title_suffixes.items():
            writer.writerow(
                {"pattern_type": "common_suffix", "pattern": pattern, "count": count}
            )
        for pattern, count in analysis.common_repeated_words.items():
            writer.writerow(
                {"pattern_type": "repeated_word", "pattern": pattern, "count": count}
            )


def _issue_row(issue: ProductIssue) -> dict[str, object]:
    product = issue.product
    return {
        "product_id": product.id,
        "title": product.title,
        "handle": product.handle,
        "status": product.status,
        "product_type": product.product_type or "",
        "vendor": product.vendor or "",
        "collections": "; ".join(product.collections),
        "tags": "; ".join(product.tags),
        "total_inventory": product.total_inventory,
        "issue_type": issue.issue_type,
        "details": issue.details,
    }


def _group_row(group: GroupAnalysis) -> dict[str, object]:
    return {
        "group_type": group.group_type,
        "group_name": group.group_name,
        "product_count": group.product_count,
        "active_count": group.active_count,
        "in_stock_count": group.in_stock_count,
        "missing_seo_title_count": group.missing_seo_title_count,
        "missing_seo_description_count": group.missing_seo_description_count,
        "missing_image_alt_count": group.missing_image_alt_count,
        "duplicate_title_count": group.duplicate_title_count,
        "duplicate_handle_count": group.duplicate_handle_count,
        "weak_description_count": group.weak_description_count,
        "unique_title_patterns": group.unique_title_patterns,
        "may_be_too_broad": group.may_be_too_broad,
        "details": "; ".join(group.broad_reasons),
    }


def _group_table(groups: list[GroupAnalysis], group_type: str) -> list[str]:
    filtered = [group for group in groups if group.group_type == group_type]
    if not filtered:
        return ["No groups found."]
    lines = [
        "| Group | Products | Missing SEO Title | Missing SEO Description | Weak Descriptions | Patterns |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group in filtered[:25]:
        lines.append(
            f"| {group.group_name} | {group.product_count} | "
            f"{group.missing_seo_title_count} | "
            f"{group.missing_seo_description_count} | "
            f"{group.weak_description_count} | "
            f"{group.unique_title_patterns} |"
        )
    return lines


def _recommended_groups(groups: list[GroupAnalysis]) -> list[GroupAnalysis]:
    eligible = [
        group
        for group in groups
        if group.group_type in {"product_type", "collection", "category"}
        and _group_issue_count(group) > 0
    ]
    return sorted(
        eligible,
        key=lambda group: (-_group_issue_count(group), -group.product_count, group.group_name),
    )[:10]


def _group_issue_count(group: GroupAnalysis) -> int:
    return (
        group.missing_seo_title_count
        + group.missing_seo_description_count
        + group.missing_image_alt_count
        + group.duplicate_title_count
        + group.duplicate_handle_count
        + group.weak_description_count
    )


def _counter_lines(counter: dict[str, int]) -> list[str]:
    if not counter:
        return ["- None found."]
    return [f"- {name}: {count}" for name, count in list(counter.items())[:20]]
