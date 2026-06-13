"""Polite HTTP fetching: a descriptive User-Agent, a delay between requests,
and retries with backoff on transient failures."""

from __future__ import annotations

import time

import httpx

USER_AGENT = (
    "BenepisyokoIngest/0.1 (educational/research; "
    "fetches public Philippine statutes from LawPhil)"
)


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(
        self,
        delay: float = 2.0,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.delay = delay
        self.retries = retries
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def get(self, url: str) -> bytes:
        """Return the raw response body. Decoding is left to the parser, which
        detects the page's (often legacy, non-UTF-8) charset from the bytes."""
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                resp = self._client.get(url)
                self._last_request_at = time.monotonic()
                if resp.status_code == 404:
                    raise FetchError(f"404 Not Found: {url}")
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server error {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return resp.content
            except FetchError:
                raise  # 404 is terminal; don't retry
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.delay * attempt)  # linear backoff
        raise FetchError(f"failed after {self.retries} attempts: {url} ({last_exc})")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
