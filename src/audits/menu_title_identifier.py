from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models.product import Product

DEFAULT_MENU_PATH = Path("data/main-2025-menu.json")

BROAD_MENU_TITLES = {
    "accessories",
    "adornments",
    "aztec dancing",
    "clothing",
    "dance accessory",
    "dance accessories",
    "dance wear",
    "headwear",
    "instrument",
    "instruments",
    "jewelry",
    "kids",
    "macuahuitls",
    "media",
    "medicine",
    "men",
    "necklaces",
    "obsidian",
    "women",
}

IDENTIFIER_ALIASES = {
    "babies": "Onesie",
    "beanies": "Beanie",
    "books": "Book",
    "bracelet": "Bracelet",
    "bracelets": "Bracelet",
    "cds": "CD",
    "crop top hoodies": "Crop Top Hoodie",
    "crystal  necklaces": "Crystal Necklace",
    "dvds": "DVD",
    "earring": "Earring",
    "earrings": "Earring",
    "hats": "Hat",
    "hoodies": "Hoodie",
    "kid hoodies": "Kid Hoodie",
    "kid shirts": "Kid Shirt",
    "ladies tank top": "Tank Top",
    "ladies top": "Top",
    "leggings": "Leggings",
    "long sleeves": "Long Sleeve",
    "macuahuitl": "Macuahuitl",
    "macuahuitls": "Macuahuitl",
    "mens tops": "Top",
    "necklace": "Necklace",
    "necklaces": "Necklace",
    "rattle": "Sonaja",
    "rattles": "Sonaja",
    "shorts": "Shorts",
    "tank top": "Tank Top",
    "tank tops": "Tank Top",
    "tank tops - ladies": "Tank Top",
    "tank tops - men": "Tank Top",
    "top": "Top",
    "tops": "Top",
    "tops - kids": "Kid Shirt",
    "tops - ladies": "Top",
    "t-shirt": "Top",
    "t-shirts": "Top",
    "windbreakers": "Windbreaker",
    "zip-up hoodies": "Zip-Up Hoodie",
}


@dataclass(frozen=True)
class MenuTitleIdentifier:
    identifier: str
    menu_path: tuple[str, ...]
    source: str
    reason: str
    attributes: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass(frozen=True)
class MenuEntry:
    title: str
    path: tuple[str, ...]
    identifier: str
    depth: int
    is_leaf: bool


def detect_menu_title_identifier(
    product: Product,
    menu_path: Path = DEFAULT_MENU_PATH,
) -> MenuTitleIdentifier | None:
    if not menu_path.exists():
        return None

    entries = _load_menu_entries(menu_path)
    candidates = _candidate_detections(product, entries)
    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.confidence,
            len(candidate.menu_path),
            len(candidate.identifier),
        ),
        reverse=True,
    )[0]


def _candidate_detections(
    product: Product,
    entries: list[MenuEntry],
) -> list[MenuTitleIdentifier]:
    candidates: list[MenuTitleIdentifier] = []
    collection_values = [collection for collection in product.collections if collection]
    title_prefix = _title_prefix(product.title)

    for raw_collection in collection_values:
        attributes = _attributes_from_collection(raw_collection)
        collection = _normalize(raw_collection)
        aliased_identifier = _identifier_alias(collection)
        if aliased_identifier:
            entry = _best_entry_for_identifier(entries, aliased_identifier)
            candidates.append(
                MenuTitleIdentifier(
                    identifier=aliased_identifier,
                    menu_path=entry.path if entry else (raw_collection,),
                    source="collection_alias",
                    reason=f"Matched collection alias: {raw_collection}",
                    attributes=attributes,
                    confidence=0.96,
                )
            )

        for entry in entries:
            if collection == _normalize(entry.title):
                confidence = 0.92 if entry.is_leaf else 0.78
                candidates.append(
                    MenuTitleIdentifier(
                        identifier=entry.identifier,
                        menu_path=entry.path,
                        source="menu_collection",
                        reason=f"Matched product collection to menu item: {raw_collection}",
                        attributes=attributes,
                        confidence=confidence,
                    )
                )

    if title_prefix:
        aliased_prefix = _identifier_alias(_normalize(title_prefix))
        if aliased_prefix:
            entry = _best_entry_for_identifier(entries, aliased_prefix)
            candidates.append(
                MenuTitleIdentifier(
                    identifier=aliased_prefix,
                    menu_path=entry.path if entry else (title_prefix,),
                    source="title_prefix_alias",
                    reason=f"Matched title prefix alias: {title_prefix}",
                    attributes={},
                    confidence=0.90,
                )
            )

    if product.product_type:
        aliased_type = _identifier_alias(_normalize(product.product_type))
        if aliased_type:
            entry = _best_entry_for_identifier(entries, aliased_type)
            candidates.append(
                MenuTitleIdentifier(
                    identifier=aliased_type,
                    menu_path=entry.path if entry else (product.product_type,),
                    source="product_type_alias",
                    reason=f"Matched product type alias: {product.product_type}",
                    attributes={},
                    confidence=0.82,
                )
            )

    ladies_clothing_detection = _ladies_clothing_detection(product, entries)
    if ladies_clothing_detection:
        candidates.append(ladies_clothing_detection)

    zip_up_hoodie_detection = _zip_up_hoodie_detection(product, entries)
    if zip_up_hoodie_detection:
        candidates.append(zip_up_hoodie_detection)

    tecpatl_detection = _tecpatl_detection(product, entries)
    if tecpatl_detection:
        candidates.append(tecpatl_detection)

    numbered_title_detection = _numbered_title_detection(product, entries)
    if numbered_title_detection:
        candidates.append(numbered_title_detection)

    macuahuitl_attributes = _macuahuitl_attributes(product)
    if macuahuitl_attributes:
        entry = _best_entry_for_identifier(entries, "Macuahuitl")
        candidates.append(
            MenuTitleIdentifier(
                identifier="Macuahuitl",
                menu_path=entry.path if entry else ("Macuahuitl",),
                source="macuahuitl_rule",
                reason="Matched Macuahuitl title or collection with size/design attributes",
                attributes=macuahuitl_attributes,
                confidence=0.98,
            )
        )

    return _remove_broad_candidates(candidates)


def _load_menu_entries(menu_path: Path) -> list[MenuEntry]:
    menu = json.loads(menu_path.read_text(encoding="utf-8"))
    entries: list[MenuEntry] = []

    def walk(items: list[dict[str, Any]], parents: tuple[str, ...]) -> None:
        for item in items:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            children = list(item.get("items") or [])
            path = (*parents, title)
            if not _is_size_title(title):
                entries.append(
                    MenuEntry(
                        title=title,
                        path=path,
                        identifier=_identifier_from_title(title),
                        depth=len(path),
                        is_leaf=not children,
                    )
                )
            walk(children, path)

    walk(list(menu.get("items") or []), ())
    return entries


def _remove_broad_candidates(
    candidates: list[MenuTitleIdentifier],
) -> list[MenuTitleIdentifier]:
    return [
        candidate
        for candidate in candidates
        if _normalize(candidate.identifier) not in BROAD_MENU_TITLES
    ]


def _best_entry_for_identifier(
    entries: list[MenuEntry],
    identifier: str,
) -> MenuEntry | None:
    matches = [
        entry for entry in entries if _normalize(entry.identifier) == _normalize(identifier)
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda entry: (entry.is_leaf, entry.depth), reverse=True)[0]


def _best_entry_for_path(
    entries: list[MenuEntry],
    expected_path: tuple[str, ...],
) -> MenuEntry | None:
    for entry in entries:
        if tuple(_normalize(part) for part in entry.path) == tuple(
            _normalize(part) for part in expected_path
        ):
            return entry
    return None


def _identifier_from_title(title: str) -> str:
    normalized = _normalize(title)
    alias = _identifier_alias(normalized)
    if alias:
        return alias
    if normalized.endswith("ies"):
        return f"{title.strip()[:-3]}y"
    if normalized.endswith("s") and not normalized.endswith("ss"):
        return title.strip()[:-1]
    return _collapse_spaces(title)


def _identifier_alias(normalized: str) -> str | None:
    normalized_value = _normalize(normalized)
    for alias, identifier in IDENTIFIER_ALIASES.items():
        if _normalize(alias) == normalized_value:
            return identifier
    return None


def _attributes_from_collection(collection: str) -> dict[str, str]:
    normalized = _normalize(collection)
    size = _size_from_text(collection)
    if normalized.startswith("macuahuitl") and size:
        return {"Size": size}
    return {}


def _ladies_clothing_detection(
    product: Product,
    entries: list[MenuEntry],
) -> MenuTitleIdentifier | None:
    haystack = " ".join(
        [
            product.title,
            product.product_type or "",
            *product.collections,
            *product.tags,
        ]
    )
    normalized = _normalize(haystack)
    if not re.search(r"\b(ladies|women|womens|women's)\b", normalized):
        return None

    garment: str | None = None
    expected_path: tuple[str, ...] | None = None
    if "tank top" in normalized or "tank tops ladies" in normalized:
        garment = "Tank Top"
        expected_path = ("Clothing", "Women", "Tank Tops")
    elif (
        "ladies top" in normalized
        or "tops ladies" in normalized
        or "baseball top" in normalized
        or re.search(r"\btops?\b", normalized)
    ):
        garment = "Top"
        expected_path = ("Clothing", "Women", "Tops")

    if not garment or not expected_path:
        return None

    entry = _best_entry_for_path(entries, expected_path)
    return MenuTitleIdentifier(
        identifier="Ladies",
        menu_path=entry.path if entry else expected_path,
        source="ladies_clothing_rule",
        reason=f"Matched ladies clothing title or collection as {garment}",
        attributes={"Audience": "Ladies", "Garment": garment},
        confidence=0.98,
    )


def _zip_up_hoodie_detection(
    product: Product,
    entries: list[MenuEntry],
) -> MenuTitleIdentifier | None:
    haystack = " ".join(
        [
            product.title,
            product.handle,
            product.product_type or "",
            *product.collections,
            *product.tags,
        ]
    )
    normalized = _normalize(haystack)
    has_zip_up_hoodie = any(
        phrase in normalized
        for phrase in [
            "zip up hoodie",
            "full zip hoodie",
            "hoodie full zip",
            "full zip up hoodie",
            "full zip hoodie",
        ]
    ) or bool(re.search(r"\bhoodie\b.*\bfull\s+zip(?:\s+up)?\b", normalized))
    if not has_zip_up_hoodie:
        return None

    expected_path = ("Clothing", "Women", "Zip-Up Hoodies")
    entry = _best_entry_for_path(entries, expected_path)
    return MenuTitleIdentifier(
        identifier="Zip-Up Hoodie",
        menu_path=entry.path if entry else expected_path,
        source="zip_up_hoodie_rule",
        reason="Matched zip-up hoodie wording in title, handle, or collection",
        attributes={"Garment": "Zip-Up Hoodie"},
        confidence=0.99,
    )


def _tecpatl_detection(
    product: Product,
    entries: list[MenuEntry],
) -> MenuTitleIdentifier | None:
    haystack = " ".join([product.title, *product.collections])
    normalized = _normalize(haystack)
    if "tecpatl" not in normalized:
        return None

    title = _normalize_quotes(product.title)
    size = _size_from_text(title)
    if "letter opener" in normalized:
        entry = _best_entry_for_path(
            entries,
            ("Macuahuitls", "Obsidian", "Letter Openers"),
        ) or _best_entry_for_path(
            entries,
            ("Aztec Dancing", "Dance Accessories", "Obsidian", "Letter Openers"),
        )
        return MenuTitleIdentifier(
            identifier="Tecpatl",
            menu_path=entry.path if entry else ("Macuahuitls", "Obsidian", "Letter Openers"),
            source="tecpatl_rule",
            reason="Matched Tecpatl obsidian letter opener title or collection",
            attributes={
                "Type": "Obsidian Letter Opener",
                **({"Size": size} if size else {}),
            },
            confidence=0.99,
        )

    if "obsidian" in normalized and "blade" in normalized:
        detail = _tecpatl_detail_from_title(title)
        entry = _best_entry_for_path(
            entries,
            ("Macuahuitls", "Obsidian", "Blade"),
        ) or _best_entry_for_path(
            entries,
            ("Aztec Dancing", "Dance Accessories", "Obsidian", "Blade"),
        )
        return MenuTitleIdentifier(
            identifier="Tecpatl",
            menu_path=entry.path if entry else ("Macuahuitls", "Obsidian", "Blade"),
            source="tecpatl_rule",
            reason="Matched Tecpatl obsidian blade title or collection",
            attributes={
                "Type": "Obsidian Blade",
                **({"Detail": detail} if detail else {}),
                **({"Size": size} if size else {}),
            },
            confidence=0.99,
        )

    return None


def _numbered_title_detection(
    product: Product,
    entries: list[MenuEntry],
) -> MenuTitleIdentifier | None:
    title = _collapse_spaces(_normalize_quotes(product.title))
    if " - " in title:
        return None

    match = re.match(r"^(?P<stem>.+?)\s+(?P<number>\d+)$", title)
    if not match:
        return None

    stem = match.group("stem").strip()
    number = match.group("number")
    numbered_parts = _numbered_title_parts(stem)
    if not numbered_parts:
        return None
    identifier, style = numbered_parts

    entry = _best_entry_for_title_tokens(entries, stem, identifier)
    attributes = {"Number": number}
    if style:
        attributes["Style"] = style

    return MenuTitleIdentifier(
        identifier=identifier,
        menu_path=entry.path if entry else (identifier,),
        source="numbered_title_pattern",
        reason=f"Parsed numbered title family from current title: {product.title}",
        attributes=attributes,
        confidence=0.97,
    )


def _numbered_title_parts(stem: str) -> tuple[str, str] | None:
    normalized = _normalize(stem)
    noun_aliases = [
        (r"\bearrings?\b", "Earring"),
        (r"\brattles?\b", "Sonaja"),
        (r"\bnecklaces?\b", "Necklace"),
        (r"\bbracelets?\b", "Bracelet"),
        (r"\bpendants?\b", "Pendant"),
        (r"\bplugs?\b", "Plug"),
        (r"\bpatches?\b", "Patch"),
        (r"\bstickers?\b", "Sticker"),
        (r"\bkeychains?\b", "Keychain"),
        (r"\bbandanas?\b", "Bandana"),
        (r"\bbeanies?\b", "Beanie"),
        (r"\bhats?\b", "Hat"),
        (r"\bhoodies?\b", "Hoodie"),
        (r"\bwindbreakers?\b", "Windbreaker"),
        (r"\bjoggers?\b", "Joggers"),
        (r"\bleggings?\b", "Leggings"),
        (r"\bshorts?\b", "Shorts"),
        (r"\btops?\b", "Top"),
        (r"\bshirts?\b", "Top"),
        (r"\bflutes?\b", "Flute"),
        (r"\bdrums?\b", "Drum"),
        (r"\bbooks?\b", "Book"),
        (r"\bcds?\b", "CD"),
        (r"\bdvds?\b", "DVD"),
    ]
    for pattern, identifier in noun_aliases:
        if re.search(pattern, normalized):
            style = re.sub(pattern, "", stem, flags=re.IGNORECASE)
            style = _clean_numbered_style(style)
            return identifier, style

    identifier = _identifier_alias(normalized) or _identifier_from_simple_plural(stem)
    if identifier:
        return identifier, ""
    return None


def _clean_numbered_style(style: str) -> str:
    style = re.sub(r"\bn\b", "and", style, flags=re.IGNORECASE)
    style = re.sub(r"\s+", " ", style).strip(" -")
    return _title_case_phrase(style)


def _identifier_from_simple_plural(value: str) -> str | None:
    normalized = _normalize(value)
    if normalized.endswith("ies"):
        return f"{value.strip()[:-3]}y"
    if normalized.endswith("s") and not normalized.endswith("ss"):
        return value.strip()[:-1]
    return value.strip() or None


def _best_entry_for_title_tokens(
    entries: list[MenuEntry],
    stem: str,
    identifier: str,
) -> MenuEntry | None:
    stem_tokens = set(_word_tokens(stem))
    matches = [
        entry
        for entry in entries
        if entry.is_leaf and set(_word_tokens(entry.title)).issubset(stem_tokens)
    ]
    if matches:
        return sorted(matches, key=lambda entry: (len(entry.path), len(entry.title)), reverse=True)[0]
    return _best_entry_for_identifier(entries, identifier)


def _macuahuitl_attributes(product: Product) -> dict[str, str]:
    haystack = " ".join([product.title, product.handle, *product.collections])
    if "macuahuitl" not in haystack.casefold():
        return {}

    attributes: dict[str, str] = {}
    size = _size_from_text(haystack)
    design = _macuahuitl_design_from_title(product.title, size)
    if design:
        attributes["Design"] = design
    if size:
        attributes["Size"] = size
    return attributes


def _tecpatl_detail_from_title(title: str) -> str:
    detail = re.sub(r"^\s*Tecpatl\s*-\s*", "", title, flags=re.IGNORECASE)
    detail = re.sub(r"\bobsidian\s+blade\b", "", detail, flags=re.IGNORECASE)
    detail = re.sub(r"\bw\b", "with", detail, flags=re.IGNORECASE)
    detail = re.sub(r"\s+", " ", detail).strip(" -")
    return _title_case_phrase(detail)


def _macuahuitl_design_from_title(title: str, size: str | None) -> str:
    normalized = _normalize_quotes(title)
    normalized = re.sub(
        r"^\s*Macuahuitl\s*\([^)]*\)\s*-?\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    if size:
        normalized = normalized.replace(size, "")
    normalized = re.sub(r"\b\d+\s*(?:in|inch|inches)\b", "", normalized, flags=re.I)
    normalized = re.sub(r'["”]', "", normalized)
    normalized = re.sub(r"\s*-\s*", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -")
    return _collapse_spaces(normalized)


def _size_from_text(value: str) -> str | None:
    match = re.search(r"(\d{1,3})\s*(?:[\"”]|''|in\b|inch(?:es)?\b)", value, re.I)
    if not match:
        return None
    return f'{match.group(1)}"'


def _title_prefix(title: str) -> str:
    return title.split(" - ", 1)[0].strip()


def _is_size_title(title: str) -> bool:
    return _size_from_text(title) is not None and not re.search(r"[A-Za-z]", title)


def _normalize(value: str) -> str:
    normalized = _normalize_quotes(value)
    normalized = re.sub(r"[_\-/|]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().casefold()


def _normalize_quotes(value: str) -> str:
    return value.replace("“", '"').replace("”", '"').replace("″", '"')


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _word_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize(value))


def _title_case_phrase(value: str) -> str:
    words = value.split(" ")
    return " ".join(word[:1].upper() + word[1:].lower() for word in words if word)
