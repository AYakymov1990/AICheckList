from pathlib import Path

from scripts.preprocess_helpcenter import write_params
from scripts.kb_audit import audit_locale


def test_write_params(tmp_path: Path) -> None:
    out = tmp_path / "chunks"
    write_params(out, size=100, overlap=10, minimum=20, normalize_bullets=True)
    data = (out / "_params.json").read_text(encoding="utf-8")
    assert '"chunk_size_chars": 100' in data
    assert '"normalize_bullets": true' in data


def test_audit_locale_basic() -> None:
    chunks = [
        {"id": "a", "text": "short", "metadata": {"category": "Cat", "section_heading": "H1"}},
        {
            "id": "b",
            "text": "this is a much longer chunk of text",
            "metadata": {"category": "Cat", "section_heading": "H2"},
        },
    ]
    stats = audit_locale(chunks, chunk_size=50, chunk_min=5)
    assert stats["total_chunks"] == 2
    assert stats["len_min"] == 5
    assert stats["len_max"] > stats["len_min"]
    assert stats["by_category"]["Cat"] == 2
    assert stats["count_below_min"] == 0
