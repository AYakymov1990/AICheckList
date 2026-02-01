"""LLM client wrapper with REST and g4f fallbacks."""

from __future__ import annotations

from typing import Any, MutableMapping, Sequence, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from g4f.client import Client


class LLMError(Exception):
    """Raised when an LLM request fails."""


Message = MutableMapping[str, str]


class LLMClient:
    """Simple LLM client supporting REST (Interference API) with g4f fallback."""

    def __init__(
        self, base_url: str | None, api_key: str, default_model: str, provider: str | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.default_model = default_model
        self.provider = provider
        self._g4f_client: Client | None = None

    def chat(
        self,
        messages: Sequence[Message],
        model: str | None = None,
        timeout_s: float = 30.0,
    ) -> str:
        """Send chat messages, preferring REST API then falling back to g4f client."""
        model_name = model or self.default_model
        errors: list[str] = []

        if self.base_url:
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json={"model": model_name, "messages": list(messages)},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    timeout=timeout_s,
                )
                response.raise_for_status()
                text = self._extract_text(response.json())
                if text:
                    return text
                errors.append("REST API returned an empty response.")
            except httpx.RequestError as exc:
                errors.append(f"REST connection error: {exc}")
            except httpx.HTTPStatusError as exc:
                errors.append(f"REST API returned {exc.response.status_code}: {exc.response.text}")
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                errors.append(f"REST API response parsing error: {exc}")

        try:
            client = self._get_g4f_client()
            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": list(messages),
                "timeout": timeout_s,
            }
            if self.provider:
                kwargs["provider"] = self.provider
            completion = client.chat.completions.create(**kwargs)
            text = self._extract_text(completion)
            if text:
                return text
            errors.append("g4f client returned an empty response.")
        except Exception as exc:  # noqa: BLE001 - we aggregate for user-friendly error
            errors.append(f"g4f client error: {exc}")
            raise LLMError("; ".join(errors)) from exc

        raise LLMError("; ".join(errors))

    def _get_g4f_client(self) -> Client:
        if self._g4f_client is None:
            try:
                from g4f.client import Client  # type: ignore
            except ImportError as exc:  # pragma: no cover - install issue
                raise LLMError(
                    "g4f package is required for fallback mode. Install 'g4f' first."
                ) from exc
            self._g4f_client = Client()
        return self._g4f_client

    @staticmethod
    def _extract_text(completion: Any) -> str:
        """Extract assistant text from an OpenAI-like completion object or dict."""
        if isinstance(completion, dict):
            choices = completion.get("choices", []) or []
        else:
            choices = getattr(completion, "choices", []) or []

        if not choices:
            return ""

        first_choice = choices[0]
        message: Any
        if isinstance(first_choice, dict):
            message = first_choice.get("message", {})
        else:
            message = getattr(first_choice, "message", None)

        if isinstance(message, dict):
            content = message.get("content")
        else:
            content = getattr(message, "content", None)

        return "" if content is None else str(content)
