"""Google Scholar client (uses the `scholarly` library)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def search_by_title(title: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Search Google Scholar by title and return candidate metadata dicts.

    This is a synchronous wrapper; call it from a thread pool executor when
    used inside async endpoints to avoid blocking the event loop.
    """
    try:
        from scholarly import scholarly  # type: ignore[import-untyped]

        results: list[dict[str, Any]] = []
        search_query = scholarly.search_pubs(title)
        for _ in range(max_results):
            try:
                pub = next(search_query)
                bib = pub.get("bib", {})
                results.append(
                    {
                        "title": bib.get("title", ""),
                        "authors": bib.get("author", []),
                        "year": str(bib.get("pub_year", "")),
                        "venue": bib.get("venue", ""),
                        "citation_count": pub.get("num_citations", 0),
                    }
                )
            except StopIteration:
                break
        return results
    except Exception as exc:  # pragma: no cover – network / library issues
        logger.warning("Google Scholar search failed: %s", exc)
        return []
