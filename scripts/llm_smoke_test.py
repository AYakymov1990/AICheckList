"""CLI smoke test for the LLM pipeline."""

from __future__ import annotations

import argparse
import sys

from app.config import get_settings
from app.services.llm.client import LLMClient, LLMError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM smoke test using g4f/Interference API.")
    parser.add_argument("--prompt", default="Say this is a test", help="User prompt.")
    parser.add_argument(
        "--model", default=None, help="Model name (defaults to G4F_MODEL from settings)."
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="Timeout in seconds (default: 20)."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    client = LLMClient(
        base_url=settings.g4f_base_url or None,
        api_key=settings.g4f_api_key,
        default_model=settings.g4f_model,
        provider=settings.g4f_provider,
    )
    model_name = args.model or settings.g4f_model
    try:
        text = client.chat(
            messages=[{"role": "user", "content": args.prompt}],
            model=model_name,
            timeout_s=args.timeout,
        )
    except LLMError as exc:
        print(f"LLM error: {exc}", file=sys.stderr)
        return 1

    print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
