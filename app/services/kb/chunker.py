"""Chunking logic for parsed Help Center articles."""

from __future__ import annotations

from typing import List

from app.services.kb.cleaner import normalize_text
from app.services.kb.models import ArticleParsed, Chunk
from app.services.kb.scraper import slug_from_url

DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split_by_separators(text: str, max_len: int, separators: List[str]) -> List[str]:
    if len(text) <= max_len or not separators:
        return [text]
    sep = separators[0]
    parts = text.split(sep)
    chunks: List[str] = []
    buf = ""
    for part in parts:
        candidate = (buf + sep + part) if buf else part
        if len(candidate) <= max_len:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
            if len(part) > max_len and len(separators) > 1:
                chunks.extend(_split_by_separators(part, max_len, separators[1:]))
                buf = ""
            else:
                buf = part
    if buf:
        chunks.append(buf)
    # If still some chunks are too long, fallback to windowing
    final: List[str] = []
    for item in chunks:
        if len(item) <= max_len:
            final.append(item)
        else:
            window = max_len
            start = 0
            while start < len(item):
                final.append(item[start : start + window])
                start += max_len
    return final


def _apply_overlap(chunks: List[str], overlap: int) -> List[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    windowed: List[str] = []
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            windowed.append(chunk)
            continue
        prev = windowed[-1]
        prefix = prev[-overlap:] if len(prev) > overlap else prev
        combined = prefix + chunk
        windowed.append(combined)
    return windowed


def _merge_small(chunks: List[str], min_len: int, max_len: int) -> List[str]:
    if not chunks:
        return []
    merged: List[str] = []
    idx = 0
    while idx < len(chunks):
        current = chunks[idx]
        if len(current) >= min_len or idx == len(chunks) - 1:
            merged.append(current)
            idx += 1
            continue
        # try merge with next
        nxt = chunks[idx + 1]
        if len(current) + len(nxt) <= max_len:
            merged.append(current + "\n" + nxt)
            idx += 2
        else:
            merged.append(current)
            idx += 1
    return merged


def _section_chunks(section_text: str, chunk_size: int, overlap: int, min_len: int) -> List[str]:
    base_chunks = _split_by_separators(section_text, chunk_size, DEFAULT_SEPARATORS)
    base_chunks = _apply_overlap(base_chunks, overlap)
    base_chunks = _merge_small(base_chunks, min_len, chunk_size)
    return [c.strip() for c in base_chunks if c.strip()]


def _section_iter(article: ArticleParsed) -> List[tuple[int, str, str]]:
    if article.sections:
        result: List[tuple[int, str, str]] = []
        for idx, sec in enumerate(article.sections):
            heading = sec.heading or ""
            text = sec.text or ""
            if text.strip():
                result.append((idx, heading, text))
        if result:
            return result
    fallback = article.plain_text or ""
    return [(0, "(no_heading)", fallback)]


def chunk_article(
    article: ArticleParsed,
    *,
    chunk_size_chars: int,
    chunk_overlap_chars: int,
    chunk_min_chars: int,
) -> List[Chunk]:
    section_entries = _section_iter(article)
    slug = slug_from_url(article.url)
    source_hash = article.source_hash()
    chunks: List[Chunk] = []
    chunk_counter = 0
    for sec_idx, heading, raw_text in section_entries:
        norm = normalize_text(raw_text)
        if not norm:
            continue
        sec_chunks = _section_chunks(norm, chunk_size_chars, chunk_overlap_chars, chunk_min_chars)
        for sec_chunk in sec_chunks:
            chunk_id = f"{article.locale}|{slug}|{sec_idx}|{chunk_counter}"
            metadata = {
                "source_url": article.url,
                "locale": article.locale,
                "site_code": getattr(article, "site_code", article.locale),
                "category": article.category or "",
                "doc_title": article.title or "",
                "section_heading": heading,
                "chunk_index": chunk_counter,
                "char_len": len(sec_chunk),
                "source_hash": source_hash,
            }
            chunks.append(Chunk(id=chunk_id, text=sec_chunk, metadata=metadata))
            chunk_counter += 1
    return chunks
