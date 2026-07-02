from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING

from src.catalog.attribute_extractor import ProductAttributes
from src.catalog.classification_config import ClassificationConfig
from src.catalog.models import CatalogProduct
from src.catalog.utils import clean_text

if TYPE_CHECKING:
    from src.catalog.classifier import ClassifiedProduct

WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class SubgroupCandidate:
    subgroup_name: str
    product_count: int
    example_products: list[str] = field(default_factory=list)
    matching_signals: list[str] = field(default_factory=list)
    confidence_average: float = 0.0
    recommended_for_rule_creation: bool = False


def detect_subgroup(
    product: CatalogProduct,
    attributes: ProductAttributes,
    config: ClassificationConfig,
) -> tuple[str | None, list[str]]:
    signals: list[str] = []
    keyword_subgroup = _keyword_subgroup(product, config)
    if keyword_subgroup:
        signals.append(f"subgroup_keyword:{keyword_subgroup}")
        return _with_family(attributes.family, keyword_subgroup), signals

    if attributes.family and attributes.accessory_type:
        subgroup = f"{attributes.family} {attributes.accessory_type.title()}".strip()
        signals.append(f"accessory_type:{attributes.accessory_type}")
        return subgroup, signals

    if attributes.family and attributes.size:
        signals.append(f"family_size:{attributes.family}:{attributes.size}")
        return f"{attributes.family} {attributes.size}", signals

    if attributes.family and attributes.design:
        signals.append(f"family_design:{attributes.family}:{attributes.design}")
        return f"{attributes.family} {attributes.design}", signals

    if product.product_type and attributes.design:
        signals.append(f"product_type_design:{product.product_type}:{attributes.design}")
        return f"{product.product_type} {attributes.design}", signals

    if product.product_type:
        signals.append(f"product_type:{product.product_type}")
        return product.product_type, signals

    if product.collections:
        signals.append(f"collection:{product.collections[0]}")
        return product.collections[0], signals

    return None, signals


def build_subgroup_candidates(
    products: list[ClassifiedProduct],
) -> list[SubgroupCandidate]:
    groups: dict[str, list[ClassifiedProduct]] = defaultdict(list)
    for product in products:
        subgroup = product.classification.subgroup
        if subgroup:
            groups[subgroup].append(product)

    candidates: list[SubgroupCandidate] = []
    for subgroup, group_products in groups.items():
        signal_counts = Counter(
            signal
            for product in group_products
            for signal in product.classification.matched_signals
            if signal.startswith(
                (
                    "subgroup_keyword:",
                    "family_size:",
                    "family_design:",
                    "product_type:",
                    "collection:",
                    "tag:",
                    "accessory_type:",
                )
            )
        )
        confidence_average = round(
            sum(product.classification.confidence for product in group_products)
            / len(group_products),
            2,
        )
        candidates.append(
            SubgroupCandidate(
                subgroup_name=subgroup,
                product_count=len(group_products),
                example_products=[
                    product.title for product in group_products[:5]
                ],
                matching_signals=[
                    signal for signal, _ in signal_counts.most_common(8)
                ],
                confidence_average=confidence_average,
                recommended_for_rule_creation=(
                    len(group_products) >= 3 and confidence_average >= 0.65
                ),
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.product_count,
            -candidate.confidence_average,
            candidate.subgroup_name,
        ),
    )


def _keyword_subgroup(
    product: CatalogProduct,
    config: ClassificationConfig,
) -> str | None:
    text = " ".join(
        [
            product.title,
            product.handle.replace("-", " "),
            product.product_type or "",
            " ".join(product.collections),
            " ".join(product.tags),
            product.description_text,
            product.first_image_alt or "",
        ]
    )
    for subgroup, keywords in config.subgroup_keywords.items():
        for keyword in keywords:
            if _contains_phrase(text, keyword):
                return subgroup
    return None


def _with_family(family: str | None, subgroup: str) -> str:
    if not family:
        return subgroup
    if subgroup.casefold().startswith(family.casefold()):
        return subgroup
    return f"{family} {subgroup}"


def _contains_phrase(text: str, phrase: str) -> bool:
    tokens = WORD_RE.findall(clean_text(text).casefold())
    phrase_tokens = WORD_RE.findall(clean_text(phrase).casefold())
    if not tokens or not phrase_tokens:
        return False
    if len(phrase_tokens) == 1:
        normalized_phrase = _singularize(phrase_tokens[0])
        return any(_singularize(token) == normalized_phrase for token in tokens)
    window_size = len(phrase_tokens)
    normalized_phrase = [_singularize(token) for token in phrase_tokens]
    for index in range(0, len(tokens) - window_size + 1):
        if [_singularize(token) for token in tokens[index : index + window_size]] == normalized_phrase:
            return True
    return False


def _singularize(value: str) -> str:
    return value[:-1] if value.endswith("s") and len(value) > 3 else value
