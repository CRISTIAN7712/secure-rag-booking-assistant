from collections.abc import Sequence
from typing import Any

import httpx


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter cannot produce a valid response."""


class OpenRouterClient:
    def __init__(self, api_key: str, model: str, base_url: str,
                 app_name: str, site_url: str, timeout: float = 90.0) -> None:
        self._api_key = api_key
        self._model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            "HTTP-Referer": site_url, "X-Title": app_name,
        }
        self._timeout = timeout

    def complete(self, messages: Sequence[dict[str, str]]) -> tuple[str, str]:
        if not self._api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured")
        try:
            response = httpx.post(
                self._url, headers=self._headers,
                json={"model": self._model, "messages": list(messages), "temperature": 0.2},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise OpenRouterError("OpenRouter returned an empty response")
            return content.strip(), str(payload.get("model", self._model))
        except httpx.HTTPStatusError as exc:
            raise OpenRouterError(
                f"OpenRouter HTTP {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

