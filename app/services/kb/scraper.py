"""Scraper for Avto.pro Help Center pages."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Iterator, TypedDict
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

DEFAULT_RETRIES = 3
BACKOFF_SECONDS = [0.5, 1.0, 2.0]
REQUEST_TIMEOUT = 20.0


def canonicalize_url(url: str) -> str:
    """Remove query/fragment and normalize trailing slash."""
    parts = urlsplit(url)
    clean_path = parts.path.rstrip("/") or "/"
    if not clean_path.endswith("/"):
        clean_path = f"{clean_path}/"
    cleaned = parts._replace(query="", fragment="", path=clean_path)
    return urlunsplit(cleaned)


def is_helpcenter_url(url: str, base_host: str) -> bool:
    """Return True if url is on the same host and under /helpcenter/."""
    parts = urlsplit(url)
    host_match = parts.netloc == base_host
    return host_match and parts.path.startswith("/helpcenter/")


@dataclass
class FetchContext:
    session: requests.Session
    rate_limit_seconds: float
    user_agent: str
    last_request_ts: float = 0.0

    def wait_for_rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self.last_request_ts
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)

    def update_timestamp(self) -> None:
        self.last_request_ts = time.time()


class LocaleStats(TypedDict):
    downloaded: int
    skipped: int
    errors: int
    assets: int
    failed_urls: list["FailedUrl"]


class FailedUrl(TypedDict, total=False):
    url: str
    error: str
    site_code: str
    http_status: int | None


def polite_get(ctx: FetchContext, url: str) -> requests.Response:
    """GET with rate limit, retries, and backoff on 429/5xx."""
    headers = {"User-Agent": ctx.user_agent}
    for attempt in range(DEFAULT_RETRIES):
        ctx.wait_for_rate_limit()
        try:
            resp = ctx.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            ctx.update_timestamp()
        except requests.RequestException:  # network / timeout
            if attempt == DEFAULT_RETRIES - 1:
                raise
            time.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
            continue

        if resp.status_code in {429, 500, 502, 503, 504}:
            if attempt == DEFAULT_RETRIES - 1:
                resp.raise_for_status()
            delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            time.sleep(delay)
            continue
        resp.raise_for_status()
        return resp
    return resp  # pragma: no cover - logically unreachable


def parse_index(html: str, base_url: str) -> list[dict[str, str]]:
    """Parse index page into article links with categories."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    # Some locales use h1 first; categories still h2
    for h2 in soup.find_all("h2"):
        category = h2.get_text(strip=True)
        list_node = h2.find_next_sibling()
        while list_node and isinstance(list_node, Tag) and list_node.name not in {"ul", "ol"}:
            list_node = list_node.find_next_sibling()
        if not list_node or list_node.name not in {"ul", "ol"}:
            continue
        for a in list_node.find_all("a", href=True):
            href = str(a.get("href", ""))
            if not href:
                continue
            link = urljoin(base_url, href)
            if not link.startswith("http"):
                continue
            if not link.startswith(base_url):
                continue
            results.append(
                {
                    "url": canonicalize_url(link),
                    "category": category,
                    "link_text": a.get_text(strip=True),
                    "site_code": "",
                }
            )
    return results


def _clean_container(container: Tag) -> None:
    for tag in container.find_all(["header", "footer", "nav", "aside", "script", "style"]):
        tag.decompose()


def _iter_text_blocks(container: Tag) -> Iterator[str]:
    for node in container.find_all(["h1", "h2", "h3", "p", "li"]):
        text = node.get_text(separator=" ", strip=True)
        if text:
            yield text


def _detect_locale_from_html(soup: BeautifulSoup, fallback: str) -> str:
    lang = ""
    if soup.html:
        lang = str(soup.html.get("lang", "") or "")
    lang = (lang or fallback).lower()
    if "-" in lang:
        lang = lang.split("-")[0]
    return lang or fallback


def extract_article(html: str, url: str, site_code: str, category_hint: str | None = None) -> dict:
    """Extract structured fields from article HTML."""
    soup = BeautifulSoup(html, "lxml")
    locale = _detect_locale_from_html(soup, site_code)
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    container = None
    if title_tag:
        for parent in title_tag.parents:
            if getattr(parent, "name", None) in {"main", "article", "section", "div"}:
                container = parent
                break
    if container is None:
        container = soup.body or soup
    _clean_container(container)

    sections: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for element in container.descendants:
        if not isinstance(element, Tag):
            continue
        if element.name in {"h2", "h3"}:
            if current:
                sections.append(current)
            current = {"heading": element.get_text(strip=True), "text": ""}
        elif element.name in {"p", "li"} and current is not None:
            text = element.get_text(separator=" ", strip=True)
            if text:
                current["text"] = (current["text"] + "\n" + text).strip()
    if current:
        sections.append(current)

    plain_text = "\n".join(_iter_text_blocks(container)).strip()

    images = []
    for img in container.find_all("img"):
        src_raw = img.get("src")
        if not src_raw:
            continue
        src = urljoin(url, str(src_raw))
        images.append({"src": src, "alt": img.get("alt", "")})

    base_host = urlsplit(url).netloc
    outbound_links: list[str] = []
    for a in container.find_all("a", href=True):
        href = str(a.get("href", ""))
        if not href:
            continue
        link_abs = urljoin(url, href)
        if is_helpcenter_url(link_abs, base_host):
            outbound_links.append(canonicalize_url(link_abs))

    content_hash = hashlib.sha256(plain_text.encode("utf-8")).hexdigest()

    return {
        "url": canonicalize_url(url),
        "site_code": site_code,
        "locale": locale,
        "category": category_hint or "",
        "title": title,
        "sections": sections,
        "plain_text": plain_text,
        "images": images,
        "outbound_links": outbound_links,
        "content_hash": content_hash,
    }


def slug_from_url(url: str) -> str:
    parts = urlsplit(url)
    segments = [seg for seg in parts.path.split("/") if seg]
    slug = segments[-1] if segments else "index"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-") or "page"
    return slug


def save_artifacts(article: dict, raw_html: str, out_dir: Path) -> tuple[Path, Path]:
    """Save raw HTML and parsed JSON (and markdown) for an article."""
    site_code = article.get("site_code", article.get("locale", "unknown"))
    slug = slug_from_url(article["url"])
    raw_dir = out_dir / "raw" / site_code
    parsed_dir = out_dir / "parsed" / site_code
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{slug}.html"
    parsed_path = parsed_dir / f"{slug}.json"
    md_path = parsed_dir / f"{slug}.md"

    raw_path.write_text(raw_html, encoding="utf-8")
    parsed_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# {article.get('title','').strip()}"]
    for section in article.get("sections", []):
        heading = section.get("heading", "")
        text = section.get("text", "")
        if heading:
            lines.append(f"## {heading}")
        if text:
            lines.append(text)
    md_path.write_text("\n\n".join(lines).strip() + "\n", encoding="utf-8")
    return raw_path, parsed_path


def _guess_extension(content_type: str | None, src: str) -> str:
    if content_type:
        if "png" in content_type:
            return ".png"
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        if "gif" in content_type:
            return ".gif"
    match = re.search(r"\.([a-zA-Z0-9]{3,4})(?:$|\?)", src)
    return f".{match.group(1)}" if match else ".img"


def download_assets(
    images: list[dict], out_dir: Path, locale: str, session: requests.Session
) -> int:
    """Download images and attach local paths."""
    if not images:
        return 0
    assets_dir = out_dir / "assets" / locale
    assets_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    headers = {"User-Agent": "qa-checklist-bot/0.1 (local dev)"}
    for img in images:
        src = img.get("src")
        if not src:
            continue
        try:
            resp = session.get(src, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException:
            continue
        ext = _guess_extension(resp.headers.get("Content-Type"), src)
        name = hashlib.sha1(src.encode("utf-8")).hexdigest() + ext
        path = assets_dir / name
        path.write_bytes(resp.content)
        img["local_path"] = str(path)
        downloaded += 1
    return downloaded


def should_skip(parsed_path: Path, force: bool) -> bool:
    return parsed_path.exists() and not force


def scrape_locale(
    site_code: str,
    base_url: str,
    out_dir: Path,
    rate_limit: float,
    download_assets_flag: bool,
    max_pages: int,
    user_agent: str,
    force: bool,
    cookies: MozillaCookieJar | None = None,
    urls_override: list[tuple[str, str]] | None = None,
) -> LocaleStats:
    """Scrape a single site_code. Returns stats."""
    session = requests.Session()
    if cookies:
        session.cookies = cookies
    ctx = FetchContext(session=session, rate_limit_seconds=rate_limit, user_agent=user_agent)
    visited: set[str] = set()
    queue: list[tuple[str, str]] = []

    if urls_override is None:
        try:
            index_resp = polite_get(ctx, base_url)
        except Exception as exc:
            return {
                "downloaded": 0,
                "skipped": 0,
                "errors": 1,
                "assets": 0,
                "failed_urls": [
                    {
                        "url": base_url,
                        "error": str(exc),
                        "site_code": site_code,
                        "http_status": None,
                    }
                ],
            }

        links = parse_index(index_resp.text, base_url)
        queue.extend([(item["url"], item.get("category", "")) for item in links])
    else:
        queue.extend(urls_override)

    stats: LocaleStats = {
        "downloaded": 0,
        "skipped": 0,
        "errors": 0,
        "assets": 0,
        "failed_urls": [],
    }

    while queue:
        url, category = queue.pop(0)
        url = canonicalize_url(url)
        if url in visited:
            continue
        visited.add(url)
        if max_pages and stats["downloaded"] >= max_pages:
            break

        slug = slug_from_url(url)
        parsed_path = out_dir / "parsed" / site_code / f"{slug}.json"
        if should_skip(parsed_path, force):
            stats["skipped"] += 1
            continue

        try:
            resp = polite_get(ctx, url)
            html = resp.text
            article = extract_article(html, url, site_code, category)
            if download_assets_flag:
                stats["assets"] += download_assets(article["images"], out_dir, site_code, session)
            save_artifacts(article, html, out_dir)
            stats["downloaded"] += 1

            # enqueue outbound links
            for link in article["outbound_links"]:
                if link not in visited:
                    queue.append((link, category))
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            stats["errors"] += 1
            stats["failed_urls"].append(
                {"url": url, "error": str(exc), "site_code": site_code, "http_status": status}
            )
            continue

    return stats


def parse_locales_arg(locales_arg: str) -> list[str]:
    return [loc.strip() for loc in locales_arg.split(",") if loc.strip()]


def parse_sites_arg(sites_arg: str) -> list[str]:
    """Alias for site codes (replaces locales)."""
    return [loc.strip() for loc in sites_arg.split(",") if loc.strip()]
