"""Shared httpx client wrapper with simple retry on transient errors."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from weahist.config import Settings
from weahist.errors import UpstreamError

logger = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    """Thin wrapper around `httpx.Client` with bounded retries."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.http_timeout_seconds)

    def get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET `url` with `params`; return parsed JSON. Retries transient failures."""
        last_exc: Exception | None = None
        for attempt in range(self._settings.http_max_retries + 1):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("HTTP error on %s (attempt %d): %s", url, attempt + 1, exc)
            else:
                if response.status_code in _RETRY_STATUS:
                    logger.warning(
                        "Retryable status %d from %s (attempt %d)",
                        response.status_code,
                        url,
                        attempt + 1,
                    )
                elif response.is_error:
                    raise UpstreamError(
                        f"{url} returned HTTP {response.status_code}: {response.text[:200]}"
                    )
                else:
                    data = response.json()
                    if not isinstance(data, dict):
                        raise UpstreamError(f"{url} returned non-object JSON")
                    return data
            if attempt < self._settings.http_max_retries:
                time.sleep(0.5 * (2**attempt))
        raise UpstreamError(f"{url} failed after retries: {last_exc}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
