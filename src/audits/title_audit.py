from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from src.models.product import Product

MIN_TITLE_LENGTH = 10
MAX_TITLE_LENGTH = 100
EXPECTED_SEGMENTS = 3


@dataclass(frozen=True)
class TitleAuditFinding:
    product_id: str
    title: str
    issue: str


def audit_titles(products: list[Product]) -> list[TitleAuditFinding]:
    title_counts = Counter(product.title.strip().casefold() for product in products)
    findings: list[TitleAuditFinding] = []

    for product in products:
        title = product.title or ""
        normalized = title.strip()
        segments = [segment.strip() for segment in normalized.split("-")]
        product_findings = [
            issue
            for issue, is_present in {
                "Missing product type": not product.product_type,
                "Too few title segments": len(segments) < EXPECTED_SEGMENTS,
                "Too many title segments": len(segments) > EXPECTED_SEGMENTS,
                "Duplicate title": title_counts[normalized.casefold()] > 1,
                "All caps title": normalized.isupper() and any(
                    char.isalpha() for char in normalized
                ),
                "Title under 10 characters": len(normalized) < MIN_TITLE_LENGTH,
                "Title over 100 characters": len(normalized) > MAX_TITLE_LENGTH,
                "Multiple consecutive spaces": bool(re.search(r"\s{2,}", title)),
                "Unusual formatting issue": _has_unusual_formatting(normalized),
            }.items()
            if is_present
        ]
        findings.extend(
            TitleAuditFinding(product_id=product.id, title=title, issue=issue)
            for issue in product_findings
        )

    return findings


def _has_unusual_formatting(title: str) -> bool:
    return any(
        [
            bool(re.search(r"--+", title)),
            title.startswith("-"),
            title.endswith("-"),
            bool(re.search(r"\s+-|-\s{2,}", title)),
            bool(re.search(r"[^\w\s\-&'\".,()/]", title)),
        ]
    )
