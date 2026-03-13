"""DBLP Search API client with exponential-backoff retry logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DBLP_API = "https://dblp.org/search/publ/api"
_MAX_RETRIES = 5
_BASE_DELAY = 1.0  # seconds


async def _fetch_with_backoff(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Perform an HTTP GET with exponential backoff on 429/5xx responses."""
    delay = _BASE_DELAY
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.get(url, params=params)
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "DBLP returned %s; retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        delay,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as exc:
                logger.error("DBLP request error: %s", exc)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise
    return {}


def _parse_dblp_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse DBLP JSON response into a list of result dicts."""
    results: list[dict[str, Any]] = []
    try:
        hits = data.get("result", {}).get("hits", {}).get("hit", [])
        for hit in hits:
            info = hit.get("info", {})
            title = info.get("title", "")
            year = info.get("year", "")
            venue = info.get("venue", "")

            authors_raw = info.get("authors", {}).get("author", [])
            if isinstance(authors_raw, str):
                authors = [authors_raw]
            elif isinstance(authors_raw, dict):
                authors = [authors_raw.get("text", "")]
            else:
                authors = [
                    a.get("text", "") if isinstance(a, dict) else a
                    for a in authors_raw
                ]

            results.append(
                {"title": title, "authors": authors, "year": str(year), "venue": venue}
            )
    except (KeyError, TypeError, AttributeError):
        pass
    return results


async def search_by_title_and_year(
    title: str, year: str = "", max_results: int = 3
) -> list[dict[str, Any]]:
    """Search DBLP by title (and optionally year) and return candidate metadata."""
    query = title
    if year:
        query = f"{title} year:{year}"
    params = {
        "q": query,
        "format": "json",
        "h": max_results,
    }
    data = await _fetch_with_backoff(_DBLP_API, params)
    return _parse_dblp_response(data)
