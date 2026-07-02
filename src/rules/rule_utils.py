from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug or "rule"


def safe_group_name(value: str) -> str:
    return slugify(value)


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(str(value).split())
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def most_common_non_empty(values: Iterable[str | None]) -> str | None:
    counter = Counter(value for value in values if value)
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def ratio(count: int, total: int) -> float:
    return count / total if total else 0.0

