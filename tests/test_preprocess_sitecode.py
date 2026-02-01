from pathlib import Path

from app.services.kb.chunker import chunk_article
from app.services.kb.models import ArticleParsed, Section


def test_chunk_metadata_contains_site_code(tmp_path: Path) -> None:
    article = ArticleParsed(
        url="https://avtopro.es/helpcenter/test/",
        locale="es",
        site_code="es",
        category="General",
        title="Test",
        sections=[
            Section(heading="H1", text="Texto de prueba suficientemente largo para chunking.")
        ],
        plain_text=None,
        content_hash="hash123",
    )
    chunks = chunk_article(article, chunk_size_chars=200, chunk_overlap_chars=0, chunk_min_chars=50)
    assert chunks[0].metadata["site_code"] == "es"
