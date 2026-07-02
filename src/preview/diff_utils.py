from __future__ import annotations

import re


def dedupe_preserve_order(values: list[str]) -> list[str]:
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


def tags_to_append(current_tags: list[str], suggested_tags: list[str]) -> list[str]:
    current = {tag.casefold() for tag in current_tags}
    return [tag for tag in suggested_tags if tag.casefold() not in current]


def important_words_removed(current: str, suggested: str) -> bool:
    current_words = _important_words(current)
    suggested_words = _important_words(suggested)
    removed = current_words - suggested_words
    return len(removed) >= 2


def slugify_handle(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _important_words(value: str) -> set[str]:
    stop_words = {
        "and",
        "the",
        "for",
        "with",
        "inch",
        "inches",
        "product",
    }
    return {
        word
        for word in re.findall(r"[A-Za-z0-9]+", value.casefold())
        if len(word) > 3 and word not in stop_words
    }
