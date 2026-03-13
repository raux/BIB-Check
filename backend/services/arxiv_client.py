"""ArXiv API client with exponential-backoff retry logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_MAX_RETRIES = 5
_BASE_DELAY = 1.0  # seconds


async def _fetch_with_backoff(url: str, params: dict[str, Any]) -> str:
    """Perform an HTTP GET with exponential backoff on 429/5xx responses."""
    delay = _BASE_DELAY
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.get(url, params=params)
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "ArXiv returned %s; retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        delay,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                response.raise_for_status()
                return response.text
            except httpx.RequestError as exc:
                logger.error("ArXiv request error: %s", exc)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise
    return ""


def _parse_arxiv_atom(xml_text: str) -> list[dict[str, Any]]:
    """Parse Atom XML returned by the ArXiv API into a list of result dicts."""
    import xml.etree.ElementTree as ET

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    results: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return results

    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        authors = [
            author.find("atom:name", ns).text.strip()
            for author in entry.findall("atom:author", ns)
            if author.find("atom:name", ns) is not None
        ]

        year_el = entry.find("atom:published", ns)
        year = year_el.text[:4] if year_el is not None and year_el.text else ""

        id_el = entry.find("atom:id", ns)
        arxiv_id = ""
        if id_el is not None and id_el.text:
            arxiv_id = id_el.text.split("/abs/")[-1]

        results.append(
            {"title": title, "authors": authors, "year": year, "arxiv_id": arxiv_id}
        )
    return results


async def search_by_title(title: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Search ArXiv by title and return a list of candidate metadata dicts."""
    params = {
        "search_query": f"ti:{title}",
        "max_results": max_results,
        "sortBy": "relevance",
    }
    xml_text = await _fetch_with_backoff(_ARXIV_API, params)
    return _parse_arxiv_atom(xml_text)


async def search_by_id(arxiv_id: str) -> dict[str, Any] | None:
    """Fetch a single ArXiv entry by its ID."""
    params = {"id_list": arxiv_id, "max_results": 1}
    xml_text = await _fetch_with_backoff(_ARXIV_API, params)
    results = _parse_arxiv_atom(xml_text)
    return results[0] if results else None
