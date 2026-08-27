"""
Thin client around the balldontlie NBA API (https://docs.balldontlie.io/).

Deliberately hand-rolled instead of using the official SDK -- the point of
this project is to practice the engineering concerns (auth, retries, rate
limiting, pagination, error handling) rather than hide them behind a
library. That tradeoff is worth calling out explicitly: in a real job you'd
usually prefer the maintained SDK.

Design notes:
- The free tier is rate-limited to a small number of requests per minute.
  We throttle client-side (a fixed sleep between calls) rather than only
  reacting to 429s, since burning through the whole quota and then backing
  off wastes time and is more likely to get temporarily blocked.
- Retries use exponential backoff and only apply to transient failures
  (429, 5xx, network errors) -- a 4xx like a bad request or bad auth should
  fail fast and loud rather than retry into the same error three times.
- Pagination follows the API's cursor-based scheme: each response includes
  meta.next_cursor, which we pass back in as the `cursor` query param until
  it comes back null.
"""

import time
from typing import Any, Iterator

import requests

from ingestion.config import Settings
from ingestion.utils.logger import get_logger

logger = get_logger(__name__)


class BallDontLieAPIError(Exception):
    """Raised for non-retryable API errors (bad auth, bad request, etc.)."""


class BallDontLieClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"Authorization": settings.api_key})
        # Spacing between requests to stay under the per-minute rate limit,
        # e.g. 5 requests/minute -> 1 request every 12 seconds.
        self._min_interval_seconds = 60.0 / settings.requests_per_minute
        self._last_request_time: float | None = None

    def _throttle(self) -> None:
        if self._last_request_time is None:
            return
        elapsed = time.monotonic() - self._last_request_time
        remaining = self._min_interval_seconds - elapsed
        if remaining > 0:
            logger.debug("Throttling for %.1fs to respect rate limit", remaining)
            time.sleep(remaining)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.settings.base_url}{path}"
        attempt = 0

        while True:
            attempt += 1
            self._throttle()
            self._last_request_time = time.monotonic()

            try:
                response = self.session.get(
                    url, params=params, timeout=self.settings.request_timeout_seconds
                )
            except requests.RequestException as exc:
                if attempt > self.settings.max_retries:
                    raise BallDontLieAPIError(
                        f"Network error calling {url} after {attempt} attempts: {exc}"
                    ) from exc
                backoff = 2 ** attempt
                logger.warning(
                    "Network error on attempt %d (%s). Retrying in %ds.",
                    attempt, exc, backoff,
                )
                time.sleep(backoff)
                continue

            if response.status_code == 200:
                return response.json()

            if response.status_code in (401, 403):
                raise BallDontLieAPIError(
                    f"Authentication failed ({response.status_code}). "
                    "Check BALLDONTLIE_API_KEY in your .env file."
                )

            if response.status_code == 404:
                raise BallDontLieAPIError(f"Not found: {url}")

            if response.status_code == 429 or response.status_code >= 500:
                if attempt > self.settings.max_retries:
                    raise BallDontLieAPIError(
                        f"Gave up after {attempt} attempts calling {url}: "
                        f"HTTP {response.status_code}"
                    )
                backoff = 2 ** attempt
                logger.warning(
                    "Retryable error %d on attempt %d. Retrying in %ds.",
                    response.status_code, attempt, backoff,
                )
                time.sleep(backoff)
                continue

            # Any other 4xx is treated as a bad request -- fail fast, don't retry.
            raise BallDontLieAPIError(
                f"Unexpected response {response.status_code} calling {url}: "
                f"{response.text[:500]}"
            )

    def get_games(self, season: int, per_page: int = 100) -> Iterator[dict[str, Any]]:
        """
        Yield every game for a given season, transparently following
        cursor-based pagination.
        """
        cursor: int | None = None
        page_number = 1

        while True:
            params: dict[str, Any] = {"seasons[]": season, "per_page": per_page}
            if cursor is not None:
                params["cursor"] = cursor

            logger.info("Fetching games page %d (season=%d)", page_number, season)
            payload = self._get("/games", params=params)

            for game in payload.get("data", []):
                yield game

            cursor = payload.get("meta", {}).get("next_cursor")
            if not cursor:
                logger.info("Reached last page for season %d", season)
                break

            page_number += 1
