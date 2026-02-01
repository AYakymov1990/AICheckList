"""CLI runner for scraping Avto.pro Help Center."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.services.kb.scraper import parse_sites_arg, scrape_locale, extract_article, save_artifacts


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Scrape Avto.pro Help Center.")
    parser.add_argument(
        "--sites",
        default=",".join(settings.help_sites.keys()),
        help="Comma-separated site codes to scrape (ru,ua,pl,es,pt).",
    )
    parser.add_argument(
        "--out",
        default=str(settings.scrape_output_dir),
        help="Output directory root (raw/parsed/assets).",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=settings.scrape_rate_limit_seconds,
        help="Seconds between requests.",
    )
    parser.add_argument(
        "--download-assets",
        type=int,
        choices=[0, 1],
        default=1 if settings.scrape_download_assets else 0,
        help="Download images (1) or skip (0).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=settings.scrape_max_pages,
        help="Limit pages per locale (0 = unlimited).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if parsed file exists.",
    )
    parser.add_argument(
        "--cookies-file",
        default=None,
        help="Path to Netscape/Mozilla cookies.txt for auth-only pages.",
    )
    parser.add_argument(
        "--auth-state-dir",
        default=".secrets/auth",
        help="Directory with Playwright storage_state files (<site>.json) for auth-only pages.",
    )
    return parser.parse_args()


def playwright_fetch(
    url: str, storage_state: Path, user_agent: str
) -> tuple[Optional[str], Optional[int], Optional[str]]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:  # pragma: no cover
        return None, None, f"playwright import failed: {exc}"

    html: Optional[str] = None
    status: Optional[int] = None
    err: Optional[str] = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(storage_state), user_agent=user_agent)
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
            status = response.status if response else None
            html = page.content()
            browser.close()
    except Exception as exc:  # pragma: no cover - runtime failure
        err = str(exc)
    return html, status, err


def main() -> int:
    settings = get_settings()
    args = parse_args()
    sites = parse_sites_arg(args.sites)
    out_dir = Path(args.out)
    auth_state_dir = Path(args.auth_state_dir) if args.auth_state_dir else None

    total: dict[str, int] = {"downloaded": 0, "skipped": 0, "errors": 0, "assets": 0}
    failed: list[dict] = []
    retries = {"attempted": 0, "succeeded": 0}
    for site_code in sites:
        base_url = settings.help_sites.get(site_code)
        if not base_url:
            print(f"[warn] No base URL for site '{site_code}', skipping.")
            continue
        print(f"[info] Scraping site={site_code} base={base_url}")
        stats = scrape_locale(
            site_code=site_code,
            base_url=base_url,
            out_dir=out_dir,
            rate_limit=args.rate_limit,
            download_assets_flag=bool(args.download_assets),
            max_pages=args.max_pages,
            user_agent=settings.scrape_user_agent,
            force=args.force,
            cookies=None,
        )
        print(
            f"[info] {site_code}: downloaded={stats['downloaded']}, "
            f"skipped={stats['skipped']}, errors={stats['errors']}, assets={stats['assets']}"
        )
        total["downloaded"] += stats["downloaded"]
        total["skipped"] += stats["skipped"]
        total["errors"] += stats["errors"]
        total["assets"] += stats["assets"]
        site_failed = [{"site_code": site_code, **item} for item in stats.get("failed_urls", [])]
        failed.extend(site_failed)

        # Playwright auth-state retry for failed pages
        if auth_state_dir and site_failed:
            state_path = auth_state_dir / f"{site_code}.json"
            if state_path.exists():
                retries["attempted"] += len(site_failed)
                remaining = []
                for item in site_failed:
                    html, status, err = playwright_fetch(
                        str(item["url"]), state_path, settings.scrape_user_agent
                    )
                    if html and "<h1" in html:
                        try:
                            article = extract_article(html, str(item["url"]), site_code, "")
                            save_artifacts(article, html, out_dir)
                            total["downloaded"] += 1
                            retries["succeeded"] += 1
                            continue
                        except Exception as exc:  # pragma: no cover
                            err = str(exc)
                    item["tried_auth_state"] = True
                    item["final_status"] = "failed_with_auth_state"
                    item["http_status"] = status
                    item["error"] = err or item.get("error", "")
                    remaining.append(item)
                # replace failed for this site with remaining
                failed = [f for f in failed if f["site_code"] != site_code] + remaining

    print(
        "[summary] total downloaded={downloaded}, skipped={skipped}, "
        "errors={errors}, assets={assets}".format(**total)
    )
    report = {"total": total, "failed_urls": failed, "retries_with_auth_state": retries}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scrape_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
