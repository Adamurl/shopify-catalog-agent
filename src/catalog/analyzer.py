from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from src.catalog.models import CatalogProduct
from src.catalog.utils import clean_text, flatten, has_text

BASIC_COLORS = {
    "black",
    "blue",
    "brown",
    "gold",
    "gray",
    "green",
    "grey",
    "orange",
    "pink",
    "purple",
    "red",
    "silver",
    "tan",
    "turquoise",
    "white",
    "yellow",
}

WEAK_DESCRIPTION_MIN_WORDS = 25
MANY_VARIANTS_THRESHOLD = 20
MANY_COLLECTIONS_THRESHOLD = 6
BROAD_GROUP_PRODUCT_COUNT = 20
BROAD_GROUP_PATTERN_COUNT = 8
BROAD_GROUP_KEYWORD_COUNT = 18

SIZE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:\"|”|inches|inch|in\.)(?=$|\s)", re.I)
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
SEPARATOR_RE = re.compile(r"\s*[-/|:]\s*")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z']+")


@dataclass(frozen=True)
class ProductIssue:
    product: CatalogProduct
    issue_type: str
    details: str


@dataclass(frozen=True)
class GroupAnalysis:
    group_type: str
    group_name: str
    product_count: int
    active_count: int
    in_stock_count: int
    missing_seo_title_count: int
    missing_seo_description_count: int
    missing_image_alt_count: int
    duplicate_title_count: int
    duplicate_handle_count: int
    weak_description_count: int
    unique_title_patterns: int
    may_be_too_broad: bool
    broad_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogAnalysis:
    products: list[CatalogProduct]
    total_products: int
    active_products: int
    in_stock_products: int
    missing_seo_title: list[ProductIssue]
    missing_seo_description: list[ProductIssue]
    missing_first_image_alt: list[ProductIssue]
    no_images: list[ProductIssue]
    duplicate_titles: list[ProductIssue]
    duplicate_handles: list[ProductIssue]
    missing_product_type: list[ProductIssue]
    missing_tags: list[ProductIssue]
    weak_descriptions: list[ProductIssue]
    numbers_at_title_end: list[ProductIssue]
    many_variants: list[ProductIssue]
    many_collections: list[ProductIssue]
    title_patterns: dict[str, int]
    common_title_prefixes: dict[str, int]
    common_title_suffixes: dict[str, int]
    common_repeated_words: dict[str, int]
    group_analyses: list[GroupAnalysis]

    @property
    def broad_groups(self) -> list[GroupAnalysis]:
        return [group for group in self.group_analyses if group.may_be_too_broad]


def analyze_catalog(products: list[CatalogProduct]) -> CatalogAnalysis:
    """Run deterministic catalog health checks over normalized products."""
    title_counts = _count_values(product.title for product in products)
    handle_counts = _count_values(product.handle for product in products)

    duplicate_titles = {
        title for title, count in title_counts.items() if title and count > 1
    }
    duplicate_handles = {
        handle for handle, count in handle_counts.items() if handle and count > 1
    }

    title_patterns = Counter(title_pattern(product.title) for product in products)
    prefixes = Counter(
        prefix for prefix in (_title_prefix(product.title) for product in products) if prefix
    )
    suffixes = Counter(
        suffix for suffix in (_title_suffix(product.title) for product in products) if suffix
    )
    repeated_words = _common_repeated_words(products)

    return CatalogAnalysis(
        products=products,
        total_products=len(products),
        active_products=sum(1 for product in products if product.status == "ACTIVE"),
        in_stock_products=sum(1 for product in products if product.is_in_stock),
        missing_seo_title=[
            _issue(product, "missing_seo_title", "SEO title is blank")
            for product in products
            if not has_text(product.seo_title)
        ],
        missing_seo_description=[
            _issue(product, "missing_seo_description", "SEO description is blank")
            for product in products
            if not has_text(product.seo_description)
        ],
        missing_first_image_alt=[
            _issue(product, "missing_first_image_alt", "First image alt text is blank")
            for product in products
            if product.images and not has_text(product.first_image_alt)
        ],
        no_images=[
            _issue(product, "no_images", "Product has no images or media")
            for product in products
            if not product.images
        ],
        duplicate_titles=[
            _issue(product, "duplicate_title", f"Duplicate title: {product.title}")
            for product in products
            if product.title in duplicate_titles
        ],
        duplicate_handles=[
            _issue(product, "duplicate_handle", f"Duplicate handle: {product.handle}")
            for product in products
            if product.handle in duplicate_handles
        ],
        missing_product_type=[
            _issue(product, "missing_product_type", "Product type is blank")
            for product in products
            if not has_text(product.product_type)
        ],
        missing_tags=[
            _issue(product, "missing_tags", "Product has no tags")
            for product in products
            if not product.tags
        ],
        weak_descriptions=[
            _issue(product, "weak_description", _weak_description_detail(product))
            for product in products
            if is_weak_description(product)
        ],
        numbers_at_title_end=[
            _issue(product, "title_ends_with_number", "Title ends with a bare number")
            for product in products
            if bool(re.search(r"\b\d+\s*$", product.title))
        ],
        many_variants=[
            _issue(
                product,
                "many_variants",
                f"Product has {len(product.variants)} variants",
            )
            for product in products
            if len(product.variants) >= MANY_VARIANTS_THRESHOLD
        ],
        many_collections=[
            _issue(
                product,
                "many_collections",
                f"Product belongs to {len(product.collections)} collections",
            )
            for product in products
            if len(product.collections) >= MANY_COLLECTIONS_THRESHOLD
        ],
        title_patterns=_sorted_counter(title_patterns),
        common_title_prefixes=_sorted_counter(prefixes),
        common_title_suffixes=_sorted_counter(suffixes),
        common_repeated_words=_sorted_counter(repeated_words),
        group_analyses=analyze_groups(products),
    )


def analyze_groups(products: list[CatalogProduct]) -> list[GroupAnalysis]:
    groups: dict[tuple[str, str], list[CatalogProduct]] = defaultdict(list)
    for product in products:
        _add_group(groups, "product_type", product.product_type, product)
        _add_group(groups, "vendor", product.vendor, product)
        _add_group(groups, "category", product.category, product)
        for collection in product.collections:
            _add_group(groups, "collection", collection, product)
        for tag in product.tags:
            _add_group(groups, "tag", tag, product)

    analyses = [
        _analyze_group(group_type, group_name, group_products)
        for (group_type, group_name), group_products in groups.items()
    ]
    return sorted(
        analyses,
        key=lambda group: (group.group_type, -group.product_count, group.group_name),
    )


def filter_products(
    products: list[CatalogProduct],
    category: str | None = None,
    product_type: str | None = None,
    tag: str | None = None,
    collection: str | None = None,
    vendor: str | None = None,
    status: str | None = None,
    include_inactive: bool = False,
) -> list[CatalogProduct]:
    if status:
        filtered = [p for p in products if _same(p.status, status)]
    else:
        filtered = products if include_inactive else [p for p in products if p.status == "ACTIVE"]
    if category:
        filtered = [p for p in filtered if _same(p.category, category)]
    if product_type:
        filtered = [p for p in filtered if _same(p.product_type, product_type)]
    if tag:
        filtered = [p for p in filtered if any(_same(value, tag) for value in p.tags)]
    if collection:
        filtered = [
            p
            for p in filtered
            if any(_same(value, collection) for value in p.collections)
        ]
    if vendor:
        filtered = [p for p in filtered if _same(p.vendor, vendor)]
    return filtered


def title_pattern(title: str) -> str:
    """Build an explainable title pattern such as ``{text} - {text} - {size}``."""
    normalized = SEPARATOR_RE.sub(" - ", clean_text(title))
    segments = [segment.strip() for segment in normalized.split(" - ") if segment.strip()]
    if not segments:
        return ""
    return " - ".join(_segment_pattern(segment) for segment in segments)


def is_weak_description(product: CatalogProduct) -> bool:
    word_count = len(product.description_text.split())
    if word_count == 0:
        return True
    if word_count < WEAK_DESCRIPTION_MIN_WORDS:
        return True
    return clean_text(product.description_text).casefold() == clean_text(product.title).casefold()


def _analyze_group(
    group_type: str,
    group_name: str,
    products: list[CatalogProduct],
) -> GroupAnalysis:
    title_counts = _count_values(product.title for product in products)
    handle_counts = _count_values(product.handle for product in products)
    patterns = {title_pattern(product.title) for product in products if product.title}
    product_types = {clean_text(product.product_type) for product in products if product.product_type}
    repeated_words = _common_repeated_words(products)
    prefixes = Counter(
        prefix for prefix in (_title_prefix(product.title) for product in products) if prefix
    )

    reasons: list[str] = []
    if len(products) >= BROAD_GROUP_PRODUCT_COUNT and len(patterns) >= BROAD_GROUP_PATTERN_COUNT:
        reasons.append(f"{len(patterns)} title patterns across {len(products)} products")
    if len(repeated_words) >= BROAD_GROUP_KEYWORD_COUNT:
        reasons.append(f"{len(repeated_words)} repeated keywords")
    if len(product_types) >= 4:
        reasons.append(f"{len(product_types)} product types mixed together")
    if len(products) >= BROAD_GROUP_PRODUCT_COUNT and len(prefixes) >= 8:
        reasons.append(f"{len(prefixes)} common title prefixes")
    if _tag_diversity(products) >= 4:
        reasons.append("high tag diversity")
    if _description_length_spread(products) >= 100:
        reasons.append("large description length spread")

    return GroupAnalysis(
        group_type=group_type,
        group_name=group_name,
        product_count=len(products),
        active_count=sum(1 for product in products if product.status == "ACTIVE"),
        in_stock_count=sum(1 for product in products if product.is_in_stock),
        missing_seo_title_count=sum(1 for product in products if not has_text(product.seo_title)),
        missing_seo_description_count=sum(
            1 for product in products if not has_text(product.seo_description)
        ),
        missing_image_alt_count=sum(
            1 for product in products if product.images and not has_text(product.first_image_alt)
        ),
        duplicate_title_count=sum(
            count for count in title_counts.values() if count > 1
        ),
        duplicate_handle_count=sum(
            count for count in handle_counts.values() if count > 1
        ),
        weak_description_count=sum(1 for product in products if is_weak_description(product)),
        unique_title_patterns=len(patterns),
        may_be_too_broad=bool(reasons),
        broad_reasons=reasons,
    )


def _add_group(
    groups: dict[tuple[str, str], list[CatalogProduct]],
    group_type: str,
    value: str | None,
    product: CatalogProduct,
) -> None:
    name = clean_text(value)
    if name:
        groups[(group_type, name)].append(product)


def _issue(product: CatalogProduct, issue_type: str, details: str) -> ProductIssue:
    return ProductIssue(product=product, issue_type=issue_type, details=details)


def _weak_description_detail(product: CatalogProduct) -> str:
    word_count = len(product.description_text.split())
    if word_count == 0:
        return "Description is blank"
    return f"Description has only {word_count} words"


def _segment_pattern(segment: str) -> str:
    value = SIZE_RE.sub("{size}", segment)
    value = NUMBER_RE.sub("{number}", value)
    words = WORD_RE.findall(value)
    if value.strip() in {"{size}", "{number}"}:
        return value.strip()
    if len(words) == 1 and words[0].casefold() in BASIC_COLORS:
        return "{color}"
    color_words = {word.casefold() for word in words if word.casefold() in BASIC_COLORS}
    if color_words and len(words) == len(color_words):
        return "{color}"
    return "{text}"


def _title_prefix(title: str) -> str:
    parts = SEPARATOR_RE.split(clean_text(title), maxsplit=1)
    return parts[0].strip() if parts else ""


def _title_suffix(title: str) -> str:
    parts = SEPARATOR_RE.split(clean_text(title))
    return parts[-1].strip() if len(parts) > 1 else ""


def _common_repeated_words(products: list[CatalogProduct]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for product in products:
        words = {
            word.casefold()
            for word in WORD_RE.findall(product.title)
            if len(word) > 2
        }
        counter.update(words)
    return Counter({word: count for word, count in counter.items() if count >= 3})


def _tag_diversity(products: list[CatalogProduct]) -> float:
    if not products:
        return 0
    tags = set(flatten(product.tags for product in products))
    return len(tags) / len(products)


def _description_length_spread(products: list[CatalogProduct]) -> int:
    lengths = [len(product.description_text.split()) for product in products]
    if len(lengths) < 2:
        return 0
    return max(lengths) - min(lengths)


def _count_values(values: Iterable[str]) -> Counter[str]:
    return Counter(clean_text(value) for value in values if clean_text(value))


def _same(left: str | None, right: str) -> bool:
    return clean_text(left).casefold() == clean_text(right).casefold()


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
