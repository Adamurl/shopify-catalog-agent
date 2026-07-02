from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.catalog.attribute_extractor import (
    ExtractedAttribute,
    ProductAttributes,
    extract_attributes,
)
from src.catalog.classification_config import ClassificationConfig
from src.catalog.models import CatalogProduct
from src.catalog.subgroup_detector import detect_subgroup
from src.catalog.utils import clean_text

WORD_RE = re.compile(r"[A-Za-z0-9]+")

MANY_VARIANTS_REVIEW_THRESHOLD = 20


@dataclass(frozen=True)
class ProductClassification:
    family: str | None
    subgroup: str | None
    category_intent: str | None
    is_accessory: bool
    is_variant_like: bool
    confidence: float
    matched_signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicting_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClassifiedProduct:
    id: str
    title: str
    handle: str
    status: str
    vendor: str | None
    product_type: str | None
    collections: list[str]
    tags: list[str]
    classification: ProductClassification
    attributes: ProductAttributes
    extracted_attributes: list[ExtractedAttribute]
    source_product: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "handle": self.handle,
            "status": self.status,
            "vendor": self.vendor,
            "product_type": self.product_type,
            "collections": self.collections,
            "tags": self.tags,
            "classification": self.classification.to_dict(),
            "attributes": self.attributes.to_dict(),
            "extracted_attributes": [
                attribute.to_dict() for attribute in self.extracted_attributes
            ],
            "source_product": self.source_product,
        }


def classify_products(
    products: list[CatalogProduct],
    config: ClassificationConfig,
) -> list[ClassifiedProduct]:
    return [classify_product(product, config) for product in products]


def classify_product(
    product: CatalogProduct,
    config: ClassificationConfig,
) -> ClassifiedProduct:
    attributes, extracted = extract_attributes(product, config)
    matched_signals = list(_family_signals(product, attributes.family, config))
    warnings: list[str] = []
    conflicting_signals = _conflicting_family_signals(product, attributes.family, config)

    subgroup, subgroup_signals = detect_subgroup(product, attributes, config)
    matched_signals.extend(subgroup_signals)

    if attributes.size:
        matched_signals.append(f"size:{attributes.size}")
    if attributes.material:
        matched_signals.append(f"material:{attributes.material}")
    if attributes.design:
        matched_signals.append(f"design:{attributes.design}")
    if attributes.accessory_type:
        matched_signals.append(f"accessory_type:{attributes.accessory_type}")

    is_variant_like = _is_variant_like(product, config)
    category_intent = _category_intent(attributes, product)

    if not attributes.family:
        warnings.append("family_not_detected")
    if not subgroup:
        warnings.append("subgroup_not_detected")
    if conflicting_signals:
        warnings.append("conflicting_group_signals")
    if not product.images:
        warnings.append("product_has_no_image")
    if not clean_text(product.product_type):
        warnings.append("missing_or_weak_product_type")
    if not product.tags:
        warnings.append("missing_tags")
    if len(product.variants) >= MANY_VARIANTS_REVIEW_THRESHOLD:
        warnings.append("many_variants_with_possible_naming_needs")
    if attributes.size_ambiguous:
        warnings.append("size_ambiguous")
    if attributes.color_ambiguous:
        warnings.append("color_ambiguous")
    if _has_useful_uncaptured_words(product, attributes):
        warnings.append("title_has_uncaptured_useful_words")
    if attributes.accessory_type and subgroup and "spare" not in subgroup.casefold():
        warnings.append("accessory_mixed_with_main_product_group")
    if is_variant_like:
        warnings.append("variant_like_product")

    confidence = _confidence_score(
        product=product,
        attributes=attributes,
        subgroup=subgroup,
        matched_signals=matched_signals,
        warnings=warnings,
        conflicting_signals=conflicting_signals,
        config=config,
    )
    if confidence < config.confidence_threshold:
        warnings.append("confidence_below_threshold")

    classification = ProductClassification(
        family=attributes.family,
        subgroup=subgroup,
        category_intent=category_intent,
        is_accessory=bool(attributes.accessory_type),
        is_variant_like=is_variant_like,
        confidence=confidence,
        matched_signals=sorted(set(matched_signals)),
        warnings=sorted(set(warnings)),
        conflicting_signals=conflicting_signals,
    )

    return ClassifiedProduct(
        id=product.id,
        title=product.title,
        handle=product.handle,
        status=product.status,
        vendor=product.vendor,
        product_type=product.product_type,
        collections=product.collections,
        tags=product.tags,
        classification=classification,
        attributes=attributes,
        extracted_attributes=extracted,
        source_product={
            "id": product.id,
            "title": product.title,
            "handle": product.handle,
        },
    )


def needs_manual_review(product: ClassifiedProduct, config: ClassificationConfig) -> bool:
    return (
        product.classification.confidence < config.confidence_threshold
        or bool(product.classification.warnings)
        or not product.classification.family
        or not product.classification.subgroup
    )


def _family_signals(
    product: CatalogProduct,
    family: str | None,
    config: ClassificationConfig,
) -> list[str]:
    if not family:
        return []
    signals: list[str] = []
    source_values = {
        "product_type": [product.product_type or ""],
        "collection": product.collections,
        "tag": product.tags,
        "title_contains": [product.title],
        "handle_contains": [product.handle],
    }
    keywords = config.family_keywords.get(family, [])
    for source, values in source_values.items():
        for value in values:
            if _contains_any(value, keywords):
                signals.append(f"{source}:{family if source != 'title_contains' and source != 'handle_contains' else keywords[0]}")
                break
    return signals


def _conflicting_family_signals(
    product: CatalogProduct,
    selected_family: str | None,
    config: ClassificationConfig,
) -> list[str]:
    text_values = [
        product.title,
        product.handle,
        product.product_type or "",
        *product.collections,
        *product.tags,
    ]
    detected: list[str] = []
    for family, keywords in config.family_keywords.items():
        if selected_family and family == selected_family:
            continue
        if any(_contains_any(value, keywords) for value in text_values):
            detected.append(family)
    return sorted(set(detected))


def _is_variant_like(product: CatalogProduct, config: ClassificationConfig) -> bool:
    title = product.title.casefold()
    if any(keyword.casefold() in title for keyword in config.variant_keywords):
        return True
    return len(product.variants) == 1 and product.variants[0].title.casefold() not in {
        "",
        "default",
        "default title",
    }


def _category_intent(attributes: ProductAttributes, product: CatalogProduct) -> str | None:
    if attributes.use_case and attributes.material and attributes.family:
        return f"{attributes.use_case} {attributes.material} {attributes.family}".casefold()
    if attributes.use_case and attributes.family:
        return f"{attributes.use_case} {attributes.family}".casefold()
    if product.product_type:
        return product.product_type.casefold()
    return attributes.family.casefold() if attributes.family else None


def _confidence_score(
    product: CatalogProduct,
    attributes: ProductAttributes,
    subgroup: str | None,
    matched_signals: list[str],
    warnings: list[str],
    conflicting_signals: list[str],
    config: ClassificationConfig,
) -> float:
    score = 0.0
    signal_text = " ".join(matched_signals)
    if "product_type:" in signal_text:
        score += 0.20
    if "collection:" in signal_text:
        score += 0.15
    if "tag:" in signal_text:
        score += 0.15
    if "title_contains:" in signal_text:
        score += 0.15
    if "handle_contains:" in signal_text:
        score += 0.08
    if subgroup:
        score += 0.08
    if attributes.size:
        score += 0.05
    if attributes.material:
        score += 0.04
    if attributes.design:
        score += 0.05
    if not conflicting_signals:
        score += 0.03
    if not warnings:
        score += 0.02
    return round(min(max(score, 0.0), 1.0), 2)


def _has_useful_uncaptured_words(
    product: CatalogProduct,
    attributes: ProductAttributes,
) -> bool:
    captured = {
        value.casefold()
        for value in [
            attributes.family,
            attributes.design,
            attributes.style,
            attributes.size,
            attributes.material,
            attributes.accessory_type,
            attributes.use_case,
        ]
        if value
    }
    for color in attributes.color:
        captured.add(color.casefold())
    for term in attributes.cultural_terms:
        captured.add(term.casefold())

    useful_words = [
        word
        for word in clean_text(product.title).replace("-", " ").split()
        if len(word) > 3 and not word.isdigit()
    ]
    uncaptured = [
        word
        for word in useful_words
        if not any(word.casefold() in value or value in word.casefold() for value in captured)
    ]
    return len(uncaptured) >= 3


def _contains_any(value: str, keywords: list[str]) -> bool:
    return any(_contains_phrase(value, keyword) for keyword in keywords)


def _contains_phrase(text: str, phrase: str) -> bool:
    tokens = WORD_RE.findall(text.casefold())
    phrase_tokens = WORD_RE.findall(phrase.casefold())
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
