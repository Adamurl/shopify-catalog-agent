from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, TypeVar

T = TypeVar("T")

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: object) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return WHITESPACE_RE.sub(" ", str(value)).strip()


def html_to_text(value: str | None) -> str:
    text = HTML_TAG_RE.sub(" ", value or "")
    return clean_text(text)


def has_text(value: str | None) -> bool:
    return bool(clean_text(value))


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({clean_text(value) for value in values if clean_text(value)})


def flatten(values: Iterable[Iterable[T]]) -> list[T]:
    return [item for value in values for item in value]

