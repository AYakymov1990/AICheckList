"""Capture authenticated storage state for Help Center sites using Playwright."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.config import get_settings


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Capture auth storage_state for Help Center.")
    parser.add_argument("--site", required=True, choices=list(settings.help_sites.keys()))
    parser.add_argument(
        "--out",
        default=None,
        help="Path to save storage_state (default: .secrets/auth/<site>.json)",
    )
    return parser.parse_args()


def main() -> int:
    settings = get_settings()
    args = parse_args()
    base_url = settings.help_sites[args.site]
    out_path = Path(".secrets/auth") / f"{args.site}.json" if args.out is None else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(base_url)
        print("Please log in manually in the opened browser tab.")
        print("Press ENTER here when done, or wait if stdin is not interactive.")
        try:
            input()
        except EOFError:
            import time

            # Fallback: give user time to log in when stdin is not interactive.
            time.sleep(90)
        context.storage_state(path=out_path)
        browser.close()
    print(f"Saved auth state to {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
