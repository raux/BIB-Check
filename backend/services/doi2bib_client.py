"""doi2bib client – resolve a DOI (or DOI URL) to a BibTeX entry.

Uses the same technique as https://doi2bib.org: sends a request to
``https://doi.org/<DOI>`` with ``Accept: application/x-bibtex`` so that the
DOI resolver returns the BibTeX directly.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BASE_DELAY = 1.0  # seconds

# Regex that captures a DOI (10.XXXX/…) anywhere in a string.
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s]+)")


def extract_doi(raw_input: str) -> str:
    """Extract a DOI from a plain DOI string or a URL containing one.

    Accepts formats such as:
    * ``10.1145/1234567.1234568``
    * ``https://doi.org/10.1145/1234567.1234568``
    * ``https://dx.doi.org/10.1145/1234567.1234568``
    * ``https://www.doi2bib.org/bib/10.1145/1234567.1234568``

    Returns the bare DOI string, or an empty string when no DOI is found.
    """
    raw_input = raw_input.strip()
    match = _DOI_RE.search(raw_input)
    return match.group(1) if match else ""


async def fetch_bibtex(doi: str) -> str:
    """Fetch a BibTeX entry for *doi* from doi.org.

    Returns the BibTeX string on success, or an empty string on failure.
    """
    url = f"https://doi.org/{doi}"
    headers = {"Accept": "application/x-bibtex; charset=utf-8"}
    delay = _BASE_DELAY

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "doi.org returned %s; retrying in %.1fs (attempt %d/%d)",
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
                logger.error("doi.org request error: %s", exc)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise
    return ""
