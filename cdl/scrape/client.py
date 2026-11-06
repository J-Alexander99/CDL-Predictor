"""Polite HTTP client for breakingpoint.gg.

Every page on the site is a Next.js (pages router) page whose full data is
embedded as JSON in ``<script id="__NEXT_DATA__">``. No browser is needed.
"""
from __future__ import annotations

import logging
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from cdl import config
from cdl.scrape.next_data import extract_next_data

log = logging.getLogger(__name__)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, httpx.TransportError)


class BreakingPointClient:
    def __init__(self, base_url: str = config.BASE_URL, interval_s: float = config.REQUEST_INTERVAL_S):
        self.base_url = base_url.rstrip("/")
        self.interval_s = interval_s
        self._last = 0.0
        self.requests_made = 0
        self._http = httpx.Client(
            headers={"User-Agent": config.USER_AGENT, "Accept": "text/html,application/json"},
            timeout=config.REQUEST_TIMEOUT_S,
            follow_redirects=True,
        )

    def __enter__(self) -> BreakingPointClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _throttle(self) -> None:
        wait = self.interval_s - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    @retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def get_html(self, path: str) -> str:
        self._throttle()
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        log.debug("GET %s", url)
        resp = self._http.get(url)
        self.requests_made += 1
        resp.raise_for_status()
        return resp.text

    def next_data(self, path: str) -> dict:
        """Fetch a page and return its parsed ``__NEXT_DATA__`` payload."""
        return extract_next_data(self.get_html(path), source=path)

    # Convenience wrappers -------------------------------------------------
    def match_page(self, match_id: int) -> dict:
        return self.next_data(f"/match/{match_id}/x")

    def event_page(self, event_id: int) -> dict:
        return self.next_data(f"/events/{event_id}")

    def matches_page(self) -> dict:
        return self.next_data("/matches")
