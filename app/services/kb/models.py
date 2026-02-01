"""Typed models for parsed articles and chunks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Section:
    heading: Optional[str]
    text: str


@dataclass
class ArticleParsed:
    url: str
    locale: str
    site_code: str
    category: Optional[str]
    title: Optional[str]
    sections: Optional[List[Section]]
    plain_text: Optional[str]
    content_hash: Optional[str]

    def source_hash(self) -> str:
        if self.content_hash:
            return self.content_hash
        base = (self.plain_text or "").encode("utf-8")
        return hashlib.sha256(base).hexdigest()


@dataclass
class Chunk:
    id: str
    text: str
    metadata: Dict[str, Any]
