"""Text normalization helpers."""

from __future__ import annotations

import html
import re
from typing import Callable

from app.config import get_settings

ZERO_WIDTH_PATTERN = re.compile(r"[\u200b\u200c\u200d\u2060]")
MULTISPACE_PATTERN = re.compile(r"[ \t]+")
MULTINEWLINE_PATTERN = re.compile(r"\n\s*\n\s*\n+")
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:])")
BULLET_PATTERN = re.compile(
    r"^[\-\u2022\u2023\u2043\u2219\u25E6\u204C\u204D\u2212\u2013\u2014\*]\s*", re.MULTILINE
)


def normalize_text(text: str, normalize_bullets: Callable[[], bool] | None = None) -> str:
    """Clean and normalize text for chunking."""
    settings = get_settings()
    do_bullets = normalize_bullets() if normalize_bullets else settings.normalize_bullets

    cleaned = html.unescape(text)
    cleaned = ZERO_WIDTH_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = MULTISPACE_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = MULTINEWLINE_PATTERN.sub("\n\n", cleaned)
    if do_bullets:
        cleaned = BULLET_PATTERN.sub("- ", cleaned)
    cleaned = SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
    cleaned = cleaned.strip()
    return cleaned
