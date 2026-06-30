from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.audits.family_detection import FamilyDetection, detect_product_family
from src.audits.menu_title_identifier import (
    DEFAULT_MENU_PATH,
    MenuTitleIdentifier,
    detect_menu_title_identifier,
)
from src.audits.title_cleanup import TitleCleanupSuggestion, cleanup_title
from src.models.product import Product

TITLE_SUGGESTION_COLUMNS = [
    "Product ID",
    "Handle",
    "Current Title",
    "Suggested Title",
    "Detected Product Family",
    "Menu Title Identifier",
    "Menu Path",
    "Detected Attributes",
    "Reason For Change",
    "Confidence",
    "Approve",
    "Notes",
]


@dataclass(frozen=True)
class TitleSuggestionRow:
    product_id: str
    handle: str
    current_title: str
    suggested_title: str
    detected_product_family: str
    menu_title_identifier: str
    menu_path: str
    detected_attributes: dict[str, str]
    reason_for_change: str
    confidence: float
    approve: str = ""
    notes: str = ""

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "Product ID": self.product_id,
            "Handle": self.handle,
            "Current Title": self.current_title,
            "Suggested Title": self.suggested_title,
            "Detected Product Family": self.detected_product_family,
            "Menu Title Identifier": self.menu_title_identifier,
            "Menu Path": self.menu_path,
            "Detected Attributes": json.dumps(
                self.detected_attributes,
                sort_keys=True,
                ensure_ascii=False,
            ),
            "Reason For Change": self.reason_for_change,
            "Confidence": f"{self.confidence:.2f}",
            "Approve": self.approve,
            "Notes": self.notes,
        }


@dataclass(frozen=True)
class TitleSuggestionReport:
    rows: list[TitleSuggestionRow]
    family_counts: dict[str, int]

    @property
    def total_products_reviewed(self) -> int:
        return len(self.rows)

    @property
    def total_suggestions_generated(self) -> int:
        return sum(1 for row in self.rows if row.current_title != row.suggested_title)

    @property
    def low_confidence_rows(self) -> int:
        return sum(1 for row in self.rows if row.confidence <= 0.70)


def build_title_suggestion_report(
    products: list[Product],
    menu_path: Path = DEFAULT_MENU_PATH,
) -> TitleSuggestionReport:
    rows: list[TitleSuggestionRow] = []
    families: Counter[str] = Counter()

    for product in products:
        family_detection = detect_product_family(product)
        menu_identifier = detect_menu_title_identifier(product, menu_path)
        suggestion = cleanup_title(product, family_detection, menu_identifier)
        detected_family = _display_family(family_detection, menu_identifier)
        families[detected_family] += 1
        rows.append(_build_row(product, family_detection, menu_identifier, suggestion))

    return TitleSuggestionReport(
        rows=rows,
        family_counts=dict(sorted(families.items(), key=lambda item: (-item[1], item[0]))),
    )


def write_title_suggestions_csv(
    rows: list[TitleSuggestionRow],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TITLE_SUGGESTION_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def _build_row(
    product: Product,
    family_detection: FamilyDetection,
    menu_identifier: MenuTitleIdentifier | None,
    suggestion: TitleCleanupSuggestion,
) -> TitleSuggestionRow:
    detected_attributes = {
        "family_source": family_detection.source,
        "family_reason": family_detection.reason,
        **suggestion.detected_attributes,
    }
    if menu_identifier:
        detected_attributes["menu_reason"] = menu_identifier.reason
        detected_attributes["menu_confidence"] = f"{menu_identifier.confidence:.2f}"
    return TitleSuggestionRow(
        product_id=product.id,
        handle=product.handle,
        current_title=suggestion.current_title,
        suggested_title=suggestion.suggested_title,
        detected_product_family=_display_family(family_detection, menu_identifier),
        menu_title_identifier=menu_identifier.identifier if menu_identifier else "",
        menu_path=" > ".join(menu_identifier.menu_path) if menu_identifier else "",
        detected_attributes=detected_attributes,
        reason_for_change=suggestion.reason_for_change,
        confidence=suggestion.confidence,
    )


def _display_family(
    family_detection: FamilyDetection,
    menu_identifier: MenuTitleIdentifier | None,
) -> str:
    if not menu_identifier:
        return family_detection.family

    style = menu_identifier.attributes.get("Style", "").strip()
    if style:
        return f"{menu_identifier.identifier} - {style}"

    return menu_identifier.identifier
