from __future__ import annotations

import re
from dataclasses import dataclass

from src.audits.family_detection import FamilyDetection
from src.audits.menu_title_identifier import MenuTitleIdentifier
from src.models.product import Product

AGE_GROUPS = {"adult", "youth", "baby"}
REASON_NO_CHANGE = "No change needed"


@dataclass(frozen=True)
class TitleCleanupSuggestion:
    current_title: str
    suggested_title: str
    detected_attributes: dict[str, str]
    reason_for_change: str
    confidence: float

    @property
    def changed(self) -> bool:
        return self.current_title != self.suggested_title


def cleanup_title(
    product: Product,
    family_detection: FamilyDetection,
    menu_identifier: MenuTitleIdentifier | None = None,
) -> TitleCleanupSuggestion:
    current_title = product.title or ""
    working_title = current_title.strip()
    reasons: list[str] = []
    confidence_candidates: list[float] = []

    working_title, spacing_changed = _normalize_spacing_and_hyphens(working_title)
    if spacing_changed:
        reasons.append("Normalized spacing")
        confidence_candidates.append(0.95)

    working_title, abbreviation_changed = _expand_with_abbreviation(working_title)
    if abbreviation_changed:
        reasons.append("Expanded abbreviation")
        confidence_candidates.append(0.90)

    working_title, color_changed = _normalize_color_separators(working_title)
    if color_changed:
        reasons.append("Normalized color separator")
        confidence_candidates.append(0.90)

    working_title, quote_changed = _normalize_quote_marks(working_title)
    if quote_changed:
        reasons.append("Standardized quote marks")
        confidence_candidates.append(0.95)

    working_title, macuahuitl_changed = _normalize_macuahuitl_title(
        working_title,
        menu_identifier,
    )
    if macuahuitl_changed:
        reasons.append("Applied Macuahuitl title structure")
        confidence_candidates.append(0.90)

    working_title, numbered_family_changed = _normalize_numbered_family_title(
        working_title,
        menu_identifier,
    )
    if numbered_family_changed:
        reasons.append("Applied numbered family title structure")
        confidence_candidates.append(0.88)

    working_title, zip_up_hoodie_changed = _normalize_zip_up_hoodie_title(
        working_title,
        menu_identifier,
    )
    if zip_up_hoodie_changed:
        reasons.append("Applied zip-up hoodie title structure")
        confidence_candidates.append(0.88)

    working_title, tecpatl_changed = _normalize_tecpatl_title(
        working_title,
        menu_identifier,
    )
    if tecpatl_changed:
        reasons.append("Applied Tecpatl title structure")
        confidence_candidates.append(0.90)

    working_title, ladies_clothing_changed = _normalize_ladies_clothing_title(
        working_title,
        menu_identifier,
    )
    if ladies_clothing_changed:
        reasons.append("Applied ladies clothing title structure")
        confidence_candidates.append(0.88)

    working_title, capitalization_changed = _basic_title_capitalization(working_title)
    if capitalization_changed:
        reasons.append("Applied basic title capitalization")
        confidence_candidates.append(0.95)

    working_title, identifier_changed = _apply_menu_title_identifier(
        working_title,
        menu_identifier,
    )
    if identifier_changed:
        reasons.append("Applied menu title identifier")
        confidence_candidates.append(0.88)

    working_title, reordered = _move_age_group_to_final_segment(
        working_title,
        family_detection.family,
    )
    if reordered:
        reasons.append("Moved age group to final segment")
        confidence_candidates.append(0.85)

    detected_attributes = _detect_attributes(working_title)
    if menu_identifier:
        detected_attributes.update(
            {
                "Menu Title Identifier": menu_identifier.identifier,
                "Menu Path": " > ".join(menu_identifier.menu_path),
                "Menu Match Source": menu_identifier.source,
            }
        )
        detected_attributes.update(menu_identifier.attributes)

    if not reasons:
        reason = REASON_NO_CHANGE
        confidence = 0.50 if family_detection.source == "unknown" else 0.70
    else:
        reason = ", ".join(reasons)
        confidence = min(confidence_candidates) if confidence_candidates else 0.70

    if family_detection.source == "unknown":
        confidence = min(confidence, 0.50)

    return TitleCleanupSuggestion(
        current_title=current_title,
        suggested_title=working_title,
        detected_attributes=detected_attributes,
        reason_for_change=reason,
        confidence=confidence,
    )


def _normalize_spacing_and_hyphens(title: str) -> tuple[str, bool]:
    protected_title, protected_terms = _protect_internal_hyphen_terms(title)
    normalized = re.sub(r"\s+", " ", protected_title).strip()
    normalized = re.sub(r"\s*-\s*", " - ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = _restore_internal_hyphen_terms(normalized, protected_terms)
    return normalized, normalized != title


def _expand_with_abbreviation(title: str) -> tuple[str, bool]:
    normalized = re.sub(r"\bw/\s*", "with ", title, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized, normalized != title


def _normalize_color_separators(title: str) -> tuple[str, bool]:
    normalized = re.sub(
        r"(?<=[A-Za-z])\s*/\s*(?=[A-Za-z])",
        " and ",
        title,
    )
    normalized = re.sub(
        r"\b([A-Za-z]+)\s+[Aa][Nn][Dd]\s+([A-Za-z]+)\b",
        lambda match: f"{match.group(1)} and {match.group(2)}",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized, normalized != title


def _normalize_quote_marks(title: str) -> tuple[str, bool]:
    normalized = (
        title.replace("“", '"')
        .replace("”", '"')
        .replace("″", '"')
        .replace("''", '"')
    )
    return normalized, normalized != title


def _normalize_macuahuitl_title(
    title: str,
    menu_identifier: MenuTitleIdentifier | None,
) -> tuple[str, bool]:
    if not menu_identifier or menu_identifier.identifier.casefold() != "macuahuitl":
        return title, False

    design = menu_identifier.attributes.get("Design", "").strip()
    size = menu_identifier.attributes.get("Size", "").strip()
    if not design and not size:
        return title, False

    segments = ["Macuahuitl"]
    if design:
        segments.append(design)
    if size:
        segments.append(size)
    normalized = " - ".join(segments)
    return normalized, normalized != title


def _normalize_numbered_family_title(
    title: str,
    menu_identifier: MenuTitleIdentifier | None,
) -> tuple[str, bool]:
    if not menu_identifier:
        return title, False

    style = menu_identifier.attributes.get("Style", "").strip()
    number = menu_identifier.attributes.get("Number", "").strip()
    if not number:
        return title, False

    segments = [menu_identifier.identifier]
    if style:
        segments.append(style)
    segments.append(number)
    normalized = " - ".join(segments)
    return normalized, normalized != title


def _normalize_zip_up_hoodie_title(
    title: str,
    menu_identifier: MenuTitleIdentifier | None,
) -> tuple[str, bool]:
    if not menu_identifier or menu_identifier.identifier != "Zip-Up Hoodie":
        return title, False

    segments = [segment.strip() for segment in title.split(" - ") if segment.strip()]
    if not segments:
        return title, False

    remaining = segments[:]
    first_segment = remaining[0]
    normalized_first = first_segment.casefold()
    if normalized_first == "zip-up hoodie":
        return title, False
    if normalized_first in {"full zip hoodie", "full zip-up hoodie", "hoodie full zip"}:
        remaining = remaining[1:]
    elif normalized_first == "hoodie":
        remaining = remaining[1:]
    elif normalized_first.startswith("hoodie "):
        remaining[0] = first_segment[len("hoodie ") :].strip()
    elif normalized_first.startswith("full zip hoodie "):
        remaining[0] = first_segment[len("full zip hoodie ") :].strip()

    remaining = [
        _remove_zip_up_detail(segment)
        for segment in remaining
        if _remove_zip_up_detail(segment)
    ]
    normalized = " - ".join(["Zip-Up Hoodie", *remaining])
    return normalized, normalized != title


def _normalize_tecpatl_title(
    title: str,
    menu_identifier: MenuTitleIdentifier | None,
) -> tuple[str, bool]:
    if not menu_identifier or menu_identifier.identifier != "Tecpatl":
        return title, False

    tecpatl_type = menu_identifier.attributes.get("Type", "").strip()
    detail = menu_identifier.attributes.get("Detail", "").strip()
    size = menu_identifier.attributes.get("Size", "").strip()
    if not tecpatl_type:
        return title, False

    segments = ["Tecpatl", tecpatl_type]
    if detail:
        segments.append(detail)
    if size:
        segments.append(size)
    normalized = " - ".join(segments)
    return normalized, normalized != title


def _remove_zip_up_detail(segment: str) -> str:
    cleaned = re.sub(r"\bfull\s+zip(?:-up)?\b", "", segment, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bzip-up\b", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" -")


def _normalize_ladies_clothing_title(
    title: str,
    menu_identifier: MenuTitleIdentifier | None,
) -> tuple[str, bool]:
    if not menu_identifier:
        return title, False

    if menu_identifier.attributes.get("Audience") != "Ladies":
        return title, False

    garment = menu_identifier.attributes.get("Garment", "").strip()
    if garment not in {"Top", "Tank Top"}:
        return title, False

    segments = [segment.strip() for segment in title.split(" - ") if segment.strip()]
    if not segments:
        return title, False

    remaining = segments[:]
    first_segment = remaining[0].casefold()
    removable_prefixes = [
        f"ladies {garment}".casefold(),
        f"women {garment}".casefold(),
        garment.casefold(),
    ]
    for prefix in removable_prefixes:
        if first_segment == prefix:
            remaining = remaining[1:]
            break
        if first_segment.startswith(f"{prefix} "):
            remaining[0] = remaining[0][len(prefix) :].strip()
            break

    if remaining:
        remaining[0] = re.sub(
            r"^(ladies|women|women's)\s+",
            "",
            remaining[0],
            flags=re.IGNORECASE,
        ).strip()
        remaining = [segment for segment in remaining if segment]

    normalized = " - ".join(["Ladies", garment, *remaining])
    return normalized, normalized != title


def _protect_internal_hyphen_terms(title: str) -> tuple[str, dict[str, str]]:
    protected_terms: dict[str, str] = {}
    protected = title
    terms = {
        "T-Shirt": r"\bT\s*-\s*Shirt\b",
        "Zip-Up": r"\bZip\s*-\s*Up\b",
        "Full-Zip": r"\bFull\s*-\s*Zip\b",
    }
    for index, (replacement, pattern) in enumerate(terms.items()):
        placeholder = f"__PROTECTED_HYPHEN_{index}__"
        protected = re.sub(pattern, placeholder, protected, flags=re.IGNORECASE)
        protected_terms[placeholder] = replacement
    return protected, protected_terms


def _restore_internal_hyphen_terms(title: str, protected_terms: dict[str, str]) -> str:
    restored = title
    for placeholder, replacement in protected_terms.items():
        restored = restored.replace(placeholder, replacement)
    return restored


def _basic_title_capitalization(title: str) -> tuple[str, bool]:
    segments = title.split(" - ")
    normalized_segments = [_capitalize_segment(segment) for segment in segments]
    normalized = " - ".join(normalized_segments)
    return normalized, normalized != title


def _capitalize_segment(segment: str) -> str:
    words = segment.split(" ")
    normalized_words = [_capitalize_word(word, index) for index, word in enumerate(words)]
    return " ".join(normalized_words)


def _capitalize_word(word: str, index: int) -> str:
    if not word:
        return word
    special_words = {
        "t-shirt": "T-Shirt",
        "zip-up": "Zip-Up",
        "full-zip": "Full-Zip",
    }
    if word.casefold() in special_words:
        return special_words[word.casefold()]
    if word.lower() == "and":
        return "and"
    if word.lower() == "with":
        return "with" if index > 0 else "With"
    if any(char.isdigit() for char in word):
        return word
    if word.isupper() and len(word) <= 3:
        return word
    if "'" in word:
        first, *rest = word.split("'")
        suffix = "'".join(part.lower() for part in rest)
        return f"{_capitalize_word(first, index)}'{suffix}"
    return word[0].upper() + word[1:].lower()


def _apply_menu_title_identifier(
    title: str,
    menu_identifier: MenuTitleIdentifier | None,
) -> tuple[str, bool]:
    if not menu_identifier:
        return title, False

    segments = [segment.strip() for segment in title.split(" - ")]
    if not segments:
        return title, False

    current_identifier = segments[0]
    target_identifier = menu_identifier.identifier.strip()
    if not target_identifier or current_identifier.casefold() == target_identifier.casefold():
        return title, False

    if not _can_replace_identifier(current_identifier, target_identifier):
        return title, False

    normalized = " - ".join([target_identifier, *segments[1:]])
    return normalized, normalized != title


def _can_replace_identifier(current_identifier: str, target_identifier: str) -> bool:
    normalized_current = current_identifier.casefold().strip()
    normalized_target = target_identifier.casefold().strip()
    safe_aliases = {
        "mens top": "top",
        "mens tops": "top",
        "t-shirt": "top",
        "t-shirts": "top",
        "tank tops": "tank top",
        "tops": "top",
    }
    return safe_aliases.get(normalized_current) == normalized_target


def _move_age_group_to_final_segment(title: str, family: str) -> tuple[str, bool]:
    if not family.casefold().startswith("ayoyotes"):
        return title, False

    segments = [segment.strip() for segment in title.split(" - ")]
    if len(segments) != 3:
        return title, False

    middle = segments[1].casefold()
    final = segments[2].casefold()
    if middle in AGE_GROUPS and final not in AGE_GROUPS:
        return " - ".join([segments[0], segments[2], segments[1]]), True
    return title, False


def _detect_attributes(title: str) -> dict[str, str]:
    segments = [segment.strip() for segment in title.split(" - ") if segment.strip()]
    attributes: dict[str, str] = {}
    if segments:
        attributes["Product"] = segments[0]
    if len(segments) >= 2:
        attributes["Attribute 1"] = segments[1]
    if len(segments) >= 3:
        attributes["Attribute 2"] = segments[2]
    return attributes
