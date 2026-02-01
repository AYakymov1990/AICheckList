"""Audit statistics for preprocessed Help Center chunks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from app.config import get_settings


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Audit Help Center chunks.")
    parser.add_argument("--chunks-root", default=str(settings.chunks_output_dir))
    parser.add_argument("--sites", default=",".join(settings.help_sites.keys()))
    return parser.parse_args()


def load_chunks(chunks_path: Path) -> List[Dict[str, Any]]:
    if not chunks_path.exists():
        return []
    items: List[Dict[str, Any]] = []
    with chunks_path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def percentile(data: List[int], q: float) -> float:
    if not data:
        return 0.0
    data_sorted = sorted(data)
    k = (len(data_sorted) - 1) * q
    f = int(k)
    c = min(f + 1, len(data_sorted) - 1)
    if f == c:
        return float(data_sorted[int(k)])
    d0 = data_sorted[f] * (c - k)
    d1 = data_sorted[c] * (k - f)
    return float(d0 + d1)


def audit_locale(chunks: List[Dict[str, Any]], chunk_size: int, chunk_min: int) -> Dict[str, Any]:
    lengths = [len(item["text"]) for item in chunks]
    meta = [item.get("metadata", {}) for item in chunks]
    cat_counts = Counter(m.get("category", "") for m in meta)
    section_counts = Counter(m.get("section_heading", "") for m in meta)
    shortest = sorted(chunks, key=lambda x: len(x["text"]))[:10]
    longest = sorted(chunks, key=lambda x: len(x["text"]), reverse=True)[:10]
    below_min = sum(1 for length in lengths if length < chunk_min)
    above_size = sum(1 for length in lengths if length > chunk_size)

    return {
        "total_chunks": len(chunks),
        "len_min": min(lengths) if lengths else 0,
        "len_max": max(lengths) if lengths else 0,
        "len_avg": mean(lengths) if lengths else 0,
        "p10": percentile(lengths, 0.10),
        "p50": percentile(lengths, 0.50),
        "p90": percentile(lengths, 0.90),
        "count_below_min": below_min,
        "count_above_size": above_size,
        "top_shortest": [item["id"] for item in shortest],
        "top_longest": [item["id"] for item in longest],
        "by_category": dict(cat_counts),
        "by_section_heading": dict(section_counts),
    }


def main() -> int:
    settings = get_settings()
    args = parse_args()
    chunk_root = Path(args.chunks_root)
    locales = [loc.strip() for loc in args.sites.split(",") if loc.strip()]
    report: Dict[str, Any] = {}
    for loc in locales:
        path = chunk_root / loc / "chunks.jsonl"
        chunks = load_chunks(path)
        report[loc] = audit_locale(chunks, settings.chunk_size_chars, settings.chunk_min_chars)

    out_path = chunk_root.parent / "audit_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[audit] saved to {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
