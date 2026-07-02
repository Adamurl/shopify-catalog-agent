from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from src.catalog.classification_config import ClassificationConfig
from src.catalog.models import CatalogProduct
from src.catalog.utils import clean_text

NUMBER_INDEX_RE = re.compile(r"(?:#|no\.?|number)\s*(\d+)", re.I)
SET_QUANTITY_RE = re.compile(r"(?:\b(\d+)\s*(?:pack|pc|piece|pieces)\b|\bset\s+of\s+(\d+)\b)", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class ExtractedAttribute:
    product_id: str
    title: str
    source_field: str
    attribute_name: str
    attribute_value: Any
    confidence: float
    extraction_rule: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductAttributes:
    family: str | None = None
    style: str | None = None
    design: str | None = None
    size: str | None = None
    size_number: int | None = None
    color: list[str] = field(default_factory=list)
    material: str | None = None
    audience: str | None = None
    gender: str | None = None
    age_group: str | None = None
    number_index: int | None = None
    set_quantity: int | None = None
    variant_type: str | None = None
    use_case: str | None = None
    cultural_terms: list[str] = field(default_factory=list)
    accessory_type: str | None = None
    size_ambiguous: bool = False
    color_ambiguous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_attributes(
    product: CatalogProduct,
    config: ClassificationConfig,
) -> tuple[ProductAttributes, list[ExtractedAttribute]]:
    extracted: list[ExtractedAttribute] = []
    sources = _source_text(product)

    family = _detect_family(product, sources, config, extracted)
    sizes = _detect_sizes(product, sources, config, extracted)
    colors = _detect_terms(product, sources, config.colors, "color", "configured_color", extracted)
    materials = _detect_terms(
        product,
        sources,
        config.materials,
        "material",
        "configured_material",
        extracted,
    )
    cultural_terms = _detect_terms(
        product,
        sources,
        config.cultural_terms,
        "cultural_terms",
        "configured_cultural_term",
        extracted,
    )
    audience = _detect_first_term(
        product,
        sources,
        config.audience_terms,
        "audience",
        "configured_audience_term",
        extracted,
    )
    gender = _detect_from_mapping(
        product,
        sources,
        config.gender_terms,
        "gender",
        "configured_gender_term",
        extracted,
    )
    age_group = _detect_from_mapping(
        product,
        sources,
        config.age_group_terms,
        "age_group",
        "configured_age_group_term",
        extracted,
    )
    use_case = _detect_from_mapping(
        product,
        sources,
        config.use_case_keywords,
        "use_case",
        "configured_use_case_keyword",
        extracted,
    )
    accessory_type = _detect_first_term(
        product,
        sources,
        config.accessory_keywords,
        "accessory_type",
        "configured_accessory_keyword",
        extracted,
    )
    number_index = _detect_number_index(product, sources, extracted)
    set_quantity = _detect_set_quantity(product, sources, extracted)
    variant_type = _detect_variant_type(product, config, extracted)
    design = _detect_design(product, family, sizes[0] if sizes else None, config, extracted)

    size_number = int(sizes[0]) if sizes else None
    size = f"{size_number} inch" if size_number is not None else None
    if size:
        _add_extracted(
            extracted,
            product,
            "title",
            "size",
            size,
            0.95,
            "normalized_size_to_inches",
        )

    attributes = ProductAttributes(
        family=family,
        style=design,
        design=design,
        size=size,
        size_number=size_number,
        color=colors,
        material=materials[0] if materials else None,
        audience=audience,
        gender=gender,
        age_group=age_group,
        number_index=number_index,
        set_quantity=set_quantity,
        variant_type=variant_type,
        use_case=use_case,
        cultural_terms=cultural_terms,
        accessory_type=accessory_type,
        size_ambiguous=len(set(sizes)) > 1,
        color_ambiguous=len(colors) > 2,
    )
    return attributes, extracted


def _source_text(product: CatalogProduct) -> dict[str, str]:
    return {
        "title": product.title,
        "handle": product.handle.replace("-", " "),
        "product_type": product.product_type or "",
        "collections": " ".join(product.collections),
        "tags": " ".join(product.tags),
        "description_text": product.description_text,
        "variant_titles": " ".join(variant.title for variant in product.variants),
        "first_image_alt": product.first_image_alt or "",
    }


def _detect_family(
    product: CatalogProduct,
    sources: dict[str, str],
    config: ClassificationConfig,
    extracted: list[ExtractedAttribute],
) -> str | None:
    scores: dict[str, float] = {}
    field_weights = {
        "product_type": 0.95,
        "collections": 0.85,
        "tags": 0.85,
        "title": 0.80,
        "handle": 0.75,
        "description_text": 0.55,
        "first_image_alt": 0.55,
        "variant_titles": 0.40,
    }
    for family, keywords in config.family_keywords.items():
        best_score = 0.0
        best_field = ""
        best_keyword = ""
        for field, text in sources.items():
            keyword = _matched_keyword(text, keywords)
            if not keyword:
                continue
            score = field_weights.get(field, 0.50)
            if score > best_score:
                best_score = score
                best_field = field
                best_keyword = keyword
        if best_score:
            scores[family] = best_score
            _add_extracted(
                extracted,
                product,
                best_field,
                "family",
                family,
                best_score,
                f"family_keyword:{best_keyword}",
            )

    if not scores:
        return None
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _detect_sizes(
    product: CatalogProduct,
    sources: dict[str, str],
    config: ClassificationConfig,
    extracted: list[ExtractedAttribute],
) -> list[int]:
    sizes: list[int] = []
    patterns = [re.compile(pattern, re.I) for pattern in config.size_patterns]
    for field in ["title", "handle", "tags", "variant_titles", "description_text"]:
        text = sources.get(field, "")
        for pattern in patterns:
            for match in pattern.finditer(text):
                value = match.groupdict().get("size") or match.group(1)
                if not value:
                    continue
                size = int(float(value))
                sizes.append(size)
                _add_extracted(
                    extracted,
                    product,
                    field,
                    "size_number",
                    size,
                    0.95 if field == "title" else 0.80,
                    "configured_size_pattern",
                )
    return sorted(set(sizes))


def _detect_terms(
    product: CatalogProduct,
    sources: dict[str, str],
    terms: list[str],
    attribute_name: str,
    rule: str,
    extracted: list[ExtractedAttribute],
) -> list[str]:
    found: dict[str, float] = {}
    for field, text in sources.items():
        for term in terms:
            if not _contains_phrase(text, term):
                continue
            found.setdefault(term, _field_confidence(field))
            _add_extracted(
                extracted,
                product,
                field,
                attribute_name,
                term,
                _field_confidence(field),
                rule,
            )
    return [term for term in terms if term in found]


def _detect_first_term(
    product: CatalogProduct,
    sources: dict[str, str],
    terms: list[str],
    attribute_name: str,
    rule: str,
    extracted: list[ExtractedAttribute],
) -> str | None:
    found = _detect_terms(product, sources, terms, attribute_name, rule, extracted)
    return found[0] if found else None


def _detect_from_mapping(
    product: CatalogProduct,
    sources: dict[str, str],
    mapping: dict[str, list[str]],
    attribute_name: str,
    rule: str,
    extracted: list[ExtractedAttribute],
) -> str | None:
    candidates: dict[str, float] = {}
    for canonical, keywords in mapping.items():
        for field, text in sources.items():
            keyword = _matched_keyword(text, keywords)
            if not keyword:
                continue
            candidates.setdefault(canonical, _field_confidence(field))
            _add_extracted(
                extracted,
                product,
                field,
                attribute_name,
                canonical,
                _field_confidence(field),
                f"{rule}:{keyword}",
            )
    if not candidates:
        return None
    return sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _detect_number_index(
    product: CatalogProduct,
    sources: dict[str, str],
    extracted: list[ExtractedAttribute],
) -> int | None:
    for field in ["title", "handle", "tags"]:
        match = NUMBER_INDEX_RE.search(sources.get(field, ""))
        if match:
            value = int(match.group(1))
            _add_extracted(
                extracted,
                product,
                field,
                "number_index",
                value,
                0.90,
                "number_index_pattern",
            )
            return value
    return None


def _detect_set_quantity(
    product: CatalogProduct,
    sources: dict[str, str],
    extracted: list[ExtractedAttribute],
) -> int | None:
    for field in ["title", "handle", "tags", "description_text"]:
        match = SET_QUANTITY_RE.search(sources.get(field, ""))
        if match:
            value = int(next(group for group in match.groups() if group))
            _add_extracted(
                extracted,
                product,
                field,
                "set_quantity",
                value,
                0.90,
                "set_quantity_pattern",
            )
            return value
    return None


def _detect_variant_type(
    product: CatalogProduct,
    config: ClassificationConfig,
    extracted: list[ExtractedAttribute],
) -> str | None:
    variant_titles = [
        clean_text(variant.title)
        for variant in product.variants
        if clean_text(variant.title).casefold() not in {"", "default", "default title"}
    ]
    if not variant_titles:
        return None
    for keyword in config.variant_keywords:
        if any(_contains_phrase(title, keyword) for title in variant_titles):
            _add_extracted(
                extracted,
                product,
                "variant_titles",
                "variant_type",
                keyword,
                0.70,
                "configured_variant_keyword",
            )
            return keyword
    return "variant"


def _detect_design(
    product: CatalogProduct,
    family: str | None,
    size_number: int | None,
    config: ClassificationConfig,
    extracted: list[ExtractedAttribute],
) -> str | None:
    segments = [segment.strip() for segment in re.split(r"\s+[-/|:]\s+", product.title) if segment.strip()]
    if len(segments) < 2:
        return None
    ignored = {family.casefold()} if family else set()
    ignored.update(term.casefold() for term in config.colors)
    ignored.update(term.casefold() for term in config.materials)
    if size_number is not None:
        ignored.add(str(size_number))

    candidates: list[str] = []
    for segment in segments:
        normalized_segment = _strip_size_terms(segment).casefold()
        if not normalized_segment:
            continue
        if any(value and value in normalized_segment for value in ignored):
            continue
        if family and family.casefold() in normalized_segment:
            continue
        candidates.append(segment)

    if not candidates:
        return None
    design = candidates[0]
    _add_extracted(
        extracted,
        product,
        "title",
        "design",
        design,
        0.75,
        "title_segment_between_family_and_attributes",
    )
    return design


def _add_extracted(
    extracted: list[ExtractedAttribute],
    product: CatalogProduct,
    source_field: str,
    attribute_name: str,
    attribute_value: Any,
    confidence: float,
    extraction_rule: str,
) -> None:
    extracted.append(
        ExtractedAttribute(
            product_id=product.id,
            title=product.title,
            source_field=source_field,
            attribute_name=attribute_name,
            attribute_value=attribute_value,
            confidence=confidence,
            extraction_rule=extraction_rule,
        )
    )


def _matched_keyword(text: str, keywords: Iterable[str]) -> str | None:
    for keyword in keywords:
        if _contains_phrase(text, keyword):
            return keyword
    return None


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


def _field_confidence(field: str) -> float:
    return {
        "title": 0.90,
        "handle": 0.80,
        "product_type": 0.90,
        "collections": 0.80,
        "tags": 0.80,
        "first_image_alt": 0.65,
        "variant_titles": 0.65,
        "description_text": 0.55,
    }.get(field, 0.50)


def _strip_size_terms(value: str) -> str:
    return re.sub(r"\b\d+(?:\.\d+)?\s*(?:\"|”|inch|inches|in\.|-inch)\b", "", value, flags=re.I).strip()


def _singularize(value: str) -> str:
    return value[:-1] if value.endswith("s") and len(value) > 3 else value
