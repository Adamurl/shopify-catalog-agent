from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.catalog.classification_config import ClassificationConfig
from src.catalog.classifier import ClassifiedProduct, needs_manual_review
from src.catalog.subgroup_detector import SubgroupCandidate, build_subgroup_candidates
from src.catalog.utils import ensure_directory, write_json

CLASSIFIED_COLUMNS = [
    "product_id",
    "title",
    "handle",
    "status",
    "product_type",
    "collections",
    "tags",
    "family",
    "subgroup",
    "size",
    "size_number",
    "color",
    "material",
    "design",
    "audience",
    "gender",
    "age_group",
    "is_accessory",
    "confidence",
    "warnings",
    "matched_signals",
]

MANUAL_REVIEW_COLUMNS = [
    "product_id",
    "title",
    "handle",
    "reason",
    "warnings",
    "confidence",
    "detected_family",
    "detected_subgroup",
    "conflicting_signals",
]

SUBGROUP_COLUMNS = [
    "subgroup_name",
    "product_count",
    "example_products",
    "matching_signals",
    "confidence_average",
    "recommended_for_rule_creation",
]

ATTRIBUTE_COLUMNS = [
    "product_id",
    "title",
    "source_field",
    "attribute_name",
    "attribute_value",
    "confidence",
    "extraction_rule",
]


def write_classification_outputs(
    products: list[ClassifiedProduct],
    classified_dir: Path,
    reports_dir: Path,
    timestamp: str,
    config: ClassificationConfig,
    filter_label: str,
) -> dict[str, Path]:
    ensure_directory(classified_dir)
    ensure_directory(reports_dir)
    subgroup_candidates = build_subgroup_candidates(products)

    paths = {
        "classified_json": classified_dir / f"classified_products_{timestamp}.json",
        "classification_summary": reports_dir / f"classification_summary_{timestamp}.md",
        "classified_products": reports_dir / f"classified_products_{timestamp}.csv",
        "manual_review": reports_dir / f"manual_review_{timestamp}.csv",
        "subgroup_candidates": reports_dir / f"subgroup_candidates_{timestamp}.csv",
        "extracted_attributes": reports_dir / f"extracted_attributes_{timestamp}.csv",
    }

    write_json(paths["classified_json"], [product.to_dict() for product in products])
    paths["classification_summary"].write_text(
        render_classification_summary(
            products,
            subgroup_candidates,
            config,
            filter_label,
        ),
        encoding="utf-8",
    )
    _write_csv(paths["classified_products"], CLASSIFIED_COLUMNS, _classified_rows(products))
    _write_csv(
        paths["manual_review"],
        MANUAL_REVIEW_COLUMNS,
        _manual_review_rows(products, config),
    )
    _write_csv(
        paths["subgroup_candidates"],
        SUBGROUP_COLUMNS,
        _subgroup_rows(subgroup_candidates),
    )
    _write_csv(
        paths["extracted_attributes"],
        ATTRIBUTE_COLUMNS,
        _attribute_rows(products),
    )
    return paths


def render_classification_summary(
    products: list[ClassifiedProduct],
    subgroup_candidates: list[SubgroupCandidate],
    config: ClassificationConfig,
    filter_label: str,
) -> str:
    manual_review = [product for product in products if needs_manual_review(product, config)]
    family_counts = Counter(
        product.classification.family or "Unclassified" for product in products
    )
    subgroup_counts = Counter(
        product.classification.subgroup or "Unclassified" for product in products
    )
    warnings = Counter(
        warning
        for product in products
        for warning in product.classification.warnings
    )
    missing_attributes = _missing_attribute_counts(products)
    conflicting = [
        product
        for product in products
        if product.classification.conflicting_signals
    ]

    lines = [
        "# Product Classification Summary",
        "",
        "READ ONLY MODE: no Shopify data was changed.",
        "",
        f"Scope: {filter_label}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total classified products | {len(products)} |",
        f"| High-confidence products | {sum(1 for product in products if product.classification.confidence >= 0.80)} |",
        f"| Products needing manual review | {len(manual_review)} |",
        f"| Detected families | {len([name for name in family_counts if name != 'Unclassified'])} |",
        f"| Detected subgroups | {len([name for name in subgroup_counts if name != 'Unclassified'])} |",
        f"| Products with conflicting groups | {len(conflicting)} |",
        "",
        "## Detected Families",
        "",
    ]
    lines.extend(_counter_lines(family_counts))
    lines.extend(["", "## Detected Subgroups", ""])
    lines.extend(_counter_lines(subgroup_counts))
    lines.extend(["", "## Common Missing Attributes", ""])
    lines.extend(_counter_lines(missing_attributes))
    lines.extend(["", "## Manual Review Warning Types", ""])
    lines.extend(_counter_lines(warnings))
    lines.extend(["", "## Conflicting Groups", ""])
    if conflicting:
        for product in conflicting[:25]:
            lines.append(
                f"- {product.title}: {', '.join(product.classification.conflicting_signals)}"
            )
    else:
        lines.append("- None found.")

    lines.extend(["", "## Recommended Next Groups For Rule Creation", ""])
    recommended = [
        candidate
        for candidate in subgroup_candidates
        if candidate.recommended_for_rule_creation
    ][:15]
    if recommended:
        for candidate in recommended:
            lines.append(
                f"- {candidate.subgroup_name}: {candidate.product_count} products, "
                f"average confidence {candidate.confidence_average}"
            )
    else:
        lines.append("- No subgroup candidates met the current rule-creation threshold.")

    lines.extend(
        [
            "",
            "## Safety Notes",
            "",
            "- Classification is deterministic and read-only.",
            "- No AI/LLM product copy was generated.",
            "- No Shopify mutations, previews, approvals, or writers were run.",
            "",
        ]
    )
    return "\n".join(lines)


def _classified_rows(products: list[ClassifiedProduct]) -> list[dict[str, Any]]:
    return [
        {
            "product_id": product.id,
            "title": product.title,
            "handle": product.handle,
            "status": product.status,
            "product_type": product.product_type or "",
            "collections": "; ".join(product.collections),
            "tags": "; ".join(product.tags),
            "family": product.classification.family or "",
            "subgroup": product.classification.subgroup or "",
            "size": product.attributes.size or "",
            "size_number": product.attributes.size_number or "",
            "color": "; ".join(product.attributes.color),
            "material": product.attributes.material or "",
            "design": product.attributes.design or "",
            "audience": product.attributes.audience or "",
            "gender": product.attributes.gender or "",
            "age_group": product.attributes.age_group or "",
            "is_accessory": product.classification.is_accessory,
            "confidence": f"{product.classification.confidence:.2f}",
            "warnings": "; ".join(product.classification.warnings),
            "matched_signals": "; ".join(product.classification.matched_signals),
        }
        for product in products
    ]


def _manual_review_rows(
    products: list[ClassifiedProduct],
    config: ClassificationConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in products:
        if not needs_manual_review(product, config):
            continue
        reasons = list(product.classification.warnings)
        if not product.classification.family:
            reasons.append("family cannot be detected")
        if not product.classification.subgroup:
            reasons.append("subgroup cannot be detected")
        rows.append(
            {
                "product_id": product.id,
                "title": product.title,
                "handle": product.handle,
                "reason": "; ".join(sorted(set(reasons))),
                "warnings": "; ".join(product.classification.warnings),
                "confidence": f"{product.classification.confidence:.2f}",
                "detected_family": product.classification.family or "",
                "detected_subgroup": product.classification.subgroup or "",
                "conflicting_signals": "; ".join(product.classification.conflicting_signals),
            }
        )
    return rows


def _subgroup_rows(candidates: list[SubgroupCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "subgroup_name": candidate.subgroup_name,
            "product_count": candidate.product_count,
            "example_products": " | ".join(candidate.example_products),
            "matching_signals": "; ".join(candidate.matching_signals),
            "confidence_average": f"{candidate.confidence_average:.2f}",
            "recommended_for_rule_creation": candidate.recommended_for_rule_creation,
        }
        for candidate in candidates
    ]


def _attribute_rows(products: list[ClassifiedProduct]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in products:
        for attribute in product.extracted_attributes:
            value = attribute.attribute_value
            rows.append(
                {
                    "product_id": attribute.product_id,
                    "title": attribute.title,
                    "source_field": attribute.source_field,
                    "attribute_name": attribute.attribute_name,
                    "attribute_value": (
                        json.dumps(value, ensure_ascii=False)
                        if isinstance(value, (list, dict))
                        else value
                    ),
                    "confidence": f"{attribute.confidence:.2f}",
                    "extraction_rule": attribute.extraction_rule,
                }
            )
    return rows


def _missing_attribute_counts(products: list[ClassifiedProduct]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for product in products:
        attributes = product.attributes
        checks = {
            "family": attributes.family,
            "subgroup": product.classification.subgroup,
            "size": attributes.size,
            "color": attributes.color,
            "material": attributes.material,
            "design": attributes.design,
            "audience": attributes.audience,
            "gender": attributes.gender,
            "age_group": attributes.age_group,
            "use_case": attributes.use_case,
        }
        for name, value in checks.items():
            if not value:
                counter[name] += 1
    return counter


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _counter_lines(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None found."]
    return [
        f"- {name}: {count}"
        for name, count in counter.most_common(25)
    ]
