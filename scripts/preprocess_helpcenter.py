"""Preprocess scraped Help Center articles into normalized chunks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List

from app.config import get_settings
from app.services.kb.chunker import chunk_article
from app.services.kb.cleaner import normalize_text
from app.services.kb.models import ArticleParsed, Section
from app.services.kb.scraper import slug_from_url, parse_sites_arg


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Preprocess Help Center articles into chunks.")
    parser.add_argument("--in", dest="inp", default=str(settings.scrape_output_dir / "parsed"))
    parser.add_argument("--out", dest="out", default=str(settings.chunks_output_dir))
    parser.add_argument("--sites", default=",".join(settings.help_sites.keys()))
    parser.add_argument("--chunk-size-chars", type=int, default=settings.chunk_size_chars)
    parser.add_argument("--chunk-overlap-chars", type=int, default=settings.chunk_overlap_chars)
    parser.add_argument("--chunk-min-chars", type=int, default=settings.chunk_min_chars)
    parser.add_argument("--also-md", type=int, choices=[0, 1], default=0)
    parser.add_argument("--format", choices=["jsonl"], default="jsonl")
    parser.add_argument("--force", type=int, choices=[0, 1], default=0)
    return parser.parse_args()


def write_params(
    out_root: Path, *, size: int, overlap: int, minimum: int, normalize_bullets: bool
) -> None:
    payload = {
        "chunk_size_chars": size,
        "chunk_overlap_chars": overlap,
        "chunk_min_chars": minimum,
        "normalize_bullets": normalize_bullets,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    params_path = out_root / "_params.json"
    params_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_article(path: Path) -> ArticleParsed:
    data = json.loads(path.read_text(encoding="utf-8"))
    sections = None
    if data.get("sections"):
        sections = [
            Section(heading=sec.get("heading"), text=sec.get("text", ""))
            for sec in data["sections"]
        ]
    return ArticleParsed(
        url=data.get("url", ""),
        locale=data.get("locale", data.get("site_code", "")),
        site_code=data.get("site_code", data.get("locale", "")),
        category=data.get("category"),
        title=data.get("title"),
        sections=sections,
        plain_text=data.get("plain_text"),
        content_hash=data.get("content_hash"),
    )


def load_index(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        hashes = data.get("article_hashes", {})
        if isinstance(hashes, dict):
            return {str(k): str(v) for k, v in hashes.items()}
        return {}
    except Exception:
        return {}


def save_index(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def preprocess_locale(
    locale: str,
    inp_dir: Path,
    out_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    chunk_min: int,
    write_md: bool,
    force: bool,
) -> dict:
    parsed_dir = inp_dir / locale
    if not parsed_dir.exists():
        return {
            "total_articles": 0,
            "total_chunks": 0,
            "avg_chunk_len": 0,
            "per_category_counts": {},
            "errors": 0,
            "article_hashes": {},
        }

    chunks_path = out_dir / locale / "chunks.jsonl"
    index_path = out_dir / locale / "index.json"
    out_dir_locale = out_dir / locale
    out_dir_locale.mkdir(parents=True, exist_ok=True)

    prev_hashes = load_index(index_path)
    per_category: Dict[str, int] = {}
    chunk_lens: List[int] = []
    total_articles = 0
    total_chunks = 0
    errors = 0
    article_hashes: Dict[str, str] = {}

    chunk_lines: List[str] = []
    for article_file in sorted(parsed_dir.glob("*.json")):
        try:
            article = load_article(article_file)
            slug = slug_from_url(article.url)
            src_hash = article.source_hash()
            if not force and prev_hashes.get(slug) == src_hash:
                continue

            chunks = chunk_article(
                article,
                chunk_size_chars=chunk_size,
                chunk_overlap_chars=chunk_overlap,
                chunk_min_chars=chunk_min,
            )
            if not chunks:
                continue
            total_articles += 1
            article_hashes[slug] = src_hash
            for ch in chunks:
                chunk_lines.append(
                    json.dumps(
                        {
                            "id": ch.id,
                            "site_code": ch.metadata.get("site_code", article.site_code),
                            "text": normalize_text(ch.text),
                            "metadata": ch.metadata,
                        },
                        ensure_ascii=False,
                    )
                )
                per_category[ch.metadata.get("category", "")] = (
                    per_category.get(ch.metadata.get("category", ""), 0) + 1
                )
                chunk_lens.append(ch.metadata["char_len"])
            total_chunks += len(chunks)

            if write_md:
                md_path = out_dir_locale / f"{slug}.md"
                md_body = "\n\n".join(ch.text for ch in chunks)
                md_path.write_text(md_body, encoding="utf-8")
        except Exception:
            errors += 1
            continue

    if chunk_lines:
        with chunks_path.open("a", encoding="utf-8") as f:
            for line in chunk_lines:
                f.write(line + "\n")

    summary = {
        "total_articles": total_articles,
        "total_chunks": total_chunks,
        "avg_chunk_len": mean(chunk_lens) if chunk_lens else 0,
        "per_category_counts": per_category,
        "errors": errors,
        "article_hashes": {**prev_hashes, **article_hashes},
    }
    save_index(index_path, summary)
    return summary


def main() -> int:
    args = parse_args()
    locales = parse_sites_arg(args.sites)
    inp_root = Path(args.inp)
    out_root = Path(args.out)

    write_params(
        out_root,
        size=args.chunk_size_chars,
        overlap=args.chunk_overlap_chars,
        minimum=args.chunk_min_chars,
        normalize_bullets=bool(get_settings().normalize_bullets),
    )

    for loc in locales:
        summary = preprocess_locale(
            locale=loc,
            inp_dir=inp_root,
            out_dir=out_root,
            chunk_size=args.chunk_size_chars,
            chunk_overlap=args.chunk_overlap_chars,
            chunk_min=args.chunk_min_chars,
            write_md=bool(args.also_md),
            force=bool(args.force),
        )
        print(
            f"[chunks] {loc}: articles={summary['total_articles']}, "
            f"chunks={summary['total_chunks']}, errors={summary['errors']}, "
            f"avg_len={summary['avg_chunk_len']:.1f}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
