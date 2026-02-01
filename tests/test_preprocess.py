from pathlib import Path

from app.services.kb.cleaner import normalize_text
from app.services.kb.chunker import chunk_article
from app.services.kb.models import ArticleParsed, Section

FIXTURES = Path(__file__).parent / "fixtures" / "preprocess"


def test_normalize_text_basic() -> None:
    raw = "Line 1  \n\n• item one\n— item two\n\n\nLine 2  "
    norm = normalize_text(raw)
    assert "- item one" in norm
    assert "- item two" in norm
    assert "\n\n\n" not in norm
    assert "  " not in norm.strip()


def test_chunk_article_by_sections() -> None:
    data = (FIXTURES / "article_two_sections.json").read_text(encoding="utf-8")
    import json

    payload = json.loads(data)
    sections = [Section(heading=sec["heading"], text=sec["text"]) for sec in payload["sections"]]
    article = ArticleParsed(
        url=payload["url"],
        locale=payload["locale"],
        site_code=payload["locale"],
        category=payload["category"],
        title=payload["title"],
        sections=sections,
        plain_text=payload["plain_text"],
        content_hash=payload["content_hash"],
    )
    chunks = chunk_article(
        article, chunk_size_chars=120, chunk_overlap_chars=20, chunk_min_chars=50
    )
    assert len(chunks) >= 2
    assert chunks[0].metadata["section_heading"] == "Intro"
    # find chunks belonging to the long "Details" section
    detail_chunks = [c for c in chunks if c.metadata["section_heading"] == "Details"]
    assert len(detail_chunks) >= 2
    assert "long paragraph" in detail_chunks[0].text
    tail = detail_chunks[0].text[-20:].strip()
    assert tail in detail_chunks[1].text
    assert chunks[0].id.startswith("ru|how-to-pay|")


def test_merge_small_chunks() -> None:
    article = ArticleParsed(
        url="https://avto.pro/helpcenter/shipping/faq/",
        locale="ru",
        site_code="ru",
        category="Shipping",
        title="Shipping FAQ",
        sections=[Section(heading=None, text="Part1 Part2 Part3")],
        plain_text="Part1 Part2 Part3",
        content_hash="hash456",
    )
    chunks = chunk_article(article, chunk_size_chars=50, chunk_overlap_chars=0, chunk_min_chars=10)
    assert len(chunks) == 1
    assert "Part1" in chunks[0].text and "Part3" in chunks[0].text
