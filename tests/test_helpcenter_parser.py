from pathlib import Path

from app.services.kb import scraper

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_canonicalize_url_strips_query_and_fragment() -> None:
    url = "https://avto.pro/helpcenter/payments/article/?utm=1#top"
    assert scraper.canonicalize_url(url) == "https://avto.pro/helpcenter/payments/article/"


def test_parse_index_extracts_links_and_categories() -> None:
    html = load_fixture("index_sample.html")
    links = scraper.parse_index(html, "https://avto.pro/helpcenter/")
    urls = [item["url"] for item in links]
    assert "https://avto.pro/helpcenter/payments/article-one/" in urls
    assert "https://avto.pro/helpcenter/payments/article-two/" in urls
    assert links[0]["category"] == "Payments"


def test_extract_article_sections_and_images() -> None:
    html = load_fixture("article_sample.html")
    article = scraper.extract_article(
        html, "https://avto.pro/helpcenter/payments/article-one/", "ru", "Payments"
    )
    assert article["title"] == "How to pay"
    assert any(sec["heading"] == "Card" for sec in article["sections"])
    assert "Daily limit" in article["plain_text"]
    assert article["images"][0]["src"].endswith("/images/card.png")
    assert article["outbound_links"] == ["https://avto.pro/helpcenter/payments/article-two/"]


def test_parse_index_es_pt() -> None:
    html_es = (FIXTURES / "index_es.html").read_text(encoding="utf-8")
    links_es = scraper.parse_index(html_es, "https://avtopro.es/helpcenter/")
    assert links_es[0]["url"] == "https://avtopro.es/helpcenter/es-article/"

    html_pt = (FIXTURES / "index_pt.html").read_text(encoding="utf-8")
    links_pt = scraper.parse_index(html_pt, "https://avtopro.pt/helpcenter/")
    assert links_pt[0]["url"] == "https://avtopro.pt/helpcenter/pt-artigo/"


def test_save_artifacts_uses_site_code(tmp_path: Path) -> None:
    article = {
        "url": "https://avtopro.pt/helpcenter/abc/",
        "site_code": "pt",
        "locale": "pt",
        "category": "",
        "title": "T",
        "sections": [],
        "plain_text": "text",
        "images": [],
        "outbound_links": [],
        "content_hash": "hash",
    }
    raw, parsed = scraper.save_artifacts(article, "<html></html>", tmp_path / "data/helpcenter")
    assert "pt" in str(raw)
    assert parsed.exists()
