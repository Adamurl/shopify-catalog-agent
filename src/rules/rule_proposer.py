from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.catalog.utils import write_json
from src.rules.rule_models import (
    ProposedRule,
    RuleConfidence,
    RuleConstraints,
    RuleExample,
    RuleFields,
    RuleMatch,
    RuleTags,
)
from src.rules.rule_utils import safe_group_name, slugify, unique_preserve_order
from src.rules.rule_validator import validate_rule
from src.rules.template_inferer import infer_templates, render_template

ClassifiedDict = dict[str, Any]

DEFAULT_MIN_GROUP_SIZE = 3
DEFAULT_MIN_CONFIDENCE = 0.8
MAX_TAGS = 8


@dataclass(frozen=True)
class RuleProposalResult:
    rules: list[ProposedRule]
    rule_paths: dict[str, Path]


def propose_rules(
    products: list[ClassifiedDict],
    output_dir: Path,
    timestamp: str,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
) -> RuleProposalResult:
    grouped = group_products_for_rules(products)
    rules: list[ProposedRule] = []
    rule_paths: dict[str, Path] = {}
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for group_name, group_products in grouped.items():
        rule = build_rule(
            group_name=group_name,
            products=group_products,
            timestamp=timestamp,
            created_at=created_at,
            min_confidence=min_confidence,
            min_group_size=min_group_size,
        )
        rules.append(rule)
        path = output_dir / f"{safe_group_name(group_name)}_rule_{timestamp}.json"
        write_json(path, rule.to_dict())
        rule_paths[rule.rule_id] = path

    return RuleProposalResult(rules=rules, rule_paths=rule_paths)


def group_products_for_rules(products: list[ClassifiedDict]) -> dict[str, list[ClassifiedDict]]:
    groups: dict[str, list[ClassifiedDict]] = defaultdict(list)
    for product in products:
        classification = _classification(product)
        group = classification.get("subgroup") or classification.get("family")
        if group:
            groups[str(group)].append(product)
    return dict(sorted(groups.items(), key=lambda item: item[0]))


def build_rule(
    group_name: str,
    products: list[ClassifiedDict],
    timestamp: str,
    created_at: str,
    min_confidence: float,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
) -> ProposedRule:
    family = _common_classification(products, "family")
    subgroup = _common_classification(products, "subgroup")
    templates = infer_templates(products)
    required_attributes = _required_attributes(products)
    confidence_score, confidence_reasons, confidence_warnings = _confidence(products, min_group_size)
    examples = _examples(products, templates)
    warnings = list(confidence_warnings)
    manual_review_conditions = [
        "missing_design",
        "missing_size",
        "low_confidence",
        "handle_change",
        "shared_media",
        "seo_description_too_long",
    ]

    rule = ProposedRule(
        rule_id=f"{slugify(group_name)}_v1",
        version=1,
        status="proposed",
        group=group_name,
        family=family,
        subgroup=subgroup,
        created_at=created_at,
        match=RuleMatch(
            family=family,
            subgroup=subgroup,
            required_attributes=required_attributes,
            exclude_if={"is_accessory": True},
            min_product_confidence=min_confidence,
        ),
        templates=templates,
        tags=RuleTags(append=_proposed_tags(products), remove=[], replace_existing=False),
        fields=RuleFields(update=["title", "seo", "tags"], leave_alone=["handle", "description", "image_alt"]),
        constraints=RuleConstraints(),
        manual_review_conditions=manual_review_conditions,
        examples=examples,
        confidence=RuleConfidence(
            score=confidence_score,
            reasons=confidence_reasons,
            warnings=warnings,
        ),
        product_count=len(products),
        source_product_ids=[str(product.get("id", "")) for product in products if product.get("id")],
    )
    validation_warnings = validate_rule(rule)
    if validation_warnings:
        rule = replace(
            rule,
            confidence=RuleConfidence(
                score=rule.confidence.score,
                reasons=rule.confidence.reasons,
                warnings=sorted(set([*rule.confidence.warnings, *validation_warnings])),
            ),
        )
    return rule


def filter_classified_products(
    products: list[ClassifiedDict],
    family: str | None = None,
    subgroup: str | None = None,
    product_type: str | None = None,
    collection: str | None = None,
    tag: str | None = None,
    vendor: str | None = None,
    min_confidence: float | None = None,
) -> list[ClassifiedDict]:
    filtered = products
    if family:
        filtered = [p for p in filtered if _same(_classification(p).get("family"), family)]
    if subgroup:
        filtered = [p for p in filtered if _same(_classification(p).get("subgroup"), subgroup)]
    if product_type:
        filtered = [p for p in filtered if _same(p.get("product_type"), product_type)]
    if collection:
        filtered = [
            p for p in filtered if any(_same(value, collection) for value in p.get("collections", []))
        ]
    if tag:
        filtered = [p for p in filtered if any(_same(value, tag) for value in p.get("tags", []))]
    if vendor:
        filtered = [p for p in filtered if _same(p.get("vendor"), vendor)]
    if min_confidence is not None:
        filtered = [
            p
            for p in filtered
            if float(_classification(p).get("confidence") or 0.0) >= min_confidence
        ]
    return filtered


def _required_attributes(products: list[ClassifiedDict]) -> dict[str, Any]:
    required: dict[str, Any] = {}
    for name in ["size", "material", "accessory_type"]:
        values = [_attributes(product).get(name) for product in products]
        counter = Counter(str(value) for value in values if value)
        if counter and counter.most_common(1)[0][1] / len(products) >= 0.75:
            required[name] = counter.most_common(1)[0][0]
    return required


def _proposed_tags(products: list[ClassifiedDict]) -> list[str]:
    values: list[str] = []
    family = _common_classification(products, "family")
    subgroup = _common_classification(products, "subgroup")
    if family:
        values.append(family)
    if subgroup and subgroup != family:
        values.append(subgroup)
    for product in products:
        attributes = _attributes(product)
        for key in ["material", "use_case"]:
            if attributes.get(key):
                values.append(str(attributes[key]))
        for term in attributes.get("cultural_terms") or []:
            values.append(str(term))
    common_tags = Counter(
        tag for product in products for tag in product.get("tags", []) if isinstance(tag, str)
    )
    values.extend(tag for tag, _ in common_tags.most_common(5))
    return unique_preserve_order(values)[:MAX_TAGS]


def _examples(products: list[ClassifiedDict], templates: Any) -> list[RuleExample]:
    examples: list[RuleExample] = []
    for product in products[:5]:
        attributes = _attributes(product)
        title = render_template(templates.title_pattern, attributes, title=str(product.get("title", "")))
        meta_title = render_template(templates.meta_title_pattern, attributes, title=title)
        meta_description = render_template(
            templates.meta_description_pattern,
            attributes,
            title=title,
        )
        examples.append(
            RuleExample(
                product_id=str(product.get("id", "")),
                current_title=str(product.get("title", "")),
                detected_attributes={
                    key: attributes.get(key)
                    for key in [
                        "family",
                        "design",
                        "size",
                        "color",
                        "material",
                        "audience",
                        "accessory_type",
                    ]
                    if attributes.get(key)
                },
                example_title=title,
                example_meta_title=meta_title,
                example_meta_description=meta_description,
            )
        )
    return examples


def _confidence(
    products: list[ClassifiedDict],
    min_group_size: int,
) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    if not products:
        return 0.0, [], ["empty_group"]

    avg_confidence = sum(float(_classification(product).get("confidence") or 0.0) for product in products) / len(products)
    score = avg_confidence
    if _all_same(products, "family"):
        score += 0.05
        reasons.append("consistent_family")
    if _all_same_attr(products, "size") and _attributes(products[0]).get("size"):
        score += 0.05
        reasons.append("consistent_size")
    if _common_title_structure(products):
        score += 0.05
        reasons.append("common_title_structure_detected")
    if len(products) < min_group_size:
        score -= 0.10
        warnings.append("small_group")
    if _accessory_mixed(products):
        score -= 0.10
        warnings.append("accessory_main_product_mixed")
    if len({_classification(product).get("family") for product in products if _classification(product).get("family")}) > 1:
        score -= 0.10
        warnings.append("too_broad_group")
    return round(min(max(score, 0.0), 1.0), 2), reasons, warnings


def _common_title_structure(products: list[ClassifiedDict]) -> bool:
    counts = Counter(str(product.get("title", "")).count(" - ") for product in products)
    return bool(counts and counts.most_common(1)[0][1] / len(products) >= 0.60)


def _accessory_mixed(products: list[ClassifiedDict]) -> bool:
    values = {_classification(product).get("is_accessory") for product in products}
    return True in values and False in values


def _all_same(products: list[ClassifiedDict], name: str) -> bool:
    values = {_classification(product).get(name) for product in products if _classification(product).get(name)}
    return len(values) == 1


def _all_same_attr(products: list[ClassifiedDict], name: str) -> bool:
    values = {_attributes(product).get(name) for product in products if _attributes(product).get(name)}
    return len(values) == 1


def _common_classification(products: list[ClassifiedDict], name: str) -> str | None:
    counter = Counter(str(_classification(product).get(name)) for product in products if _classification(product).get(name))
    return counter.most_common(1)[0][0] if counter else None


def _classification(product: ClassifiedDict) -> dict[str, Any]:
    classification = product.get("classification")
    return classification if isinstance(classification, dict) else {}


def _attributes(product: ClassifiedDict) -> dict[str, Any]:
    attributes = product.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _same(left: object, right: str) -> bool:
    return str(left or "").casefold().strip() == right.casefold().strip()
