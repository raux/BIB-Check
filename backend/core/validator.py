"""Core validation engine for BibValidate-AI.

Responsibilities
----------------
1. Parse a raw BibTeX string into :class:`BibEntry` objects.
2. Query ArXiv / DBLP / Scholar for each entry and produce
   :class:`FieldSuggestion` and :class:`ApiMatch` objects.
3. Run fuzzy duplicate detection across all entries.
4. Determine the final :class:`EntryStatus` for each entry.
5. Serialize accepted suggestions back to a BibTeX string.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from rapidfuzz import fuzz

from backend.models.schemas import (
    ApiMatch,
    BibEntry,
    DuplicateInfo,
    EntryStatus,
    FieldSuggestion,
    ParseResponse,
    ValidateResponse,
)
from backend.services import arxiv_client, dblp_client, scholar_client

logger = logging.getLogger(__name__)

# Confidence threshold above which a fix is considered "auto-applicable".
HIGH_CONFIDENCE_THRESHOLD = 0.95
# Similarity threshold (0-100 scale used by RapidFuzz) for duplicate detection.
DUPLICATE_THRESHOLD = 85.0


# ---------------------------------------------------------------------------
# BibTeX parsing helpers
# ---------------------------------------------------------------------------

def _strip_latex(text: str) -> str:
    """Remove common LaTeX commands to produce a plain-text string."""
    # Remove braces and backslash commands used for special characters
    text = re.sub(r"\{\\[\"'`^~.=](\w)\}", r"\1", text)
    text = re.sub(r"\\[\"'`^~.=]\{(\w)\}", r"\1", text)
    text = re.sub(r"\{(\w+)\}", r"\1", text)
    text = text.replace("{", "").replace("}", "")
    return text.strip()


def _parse_bibtex(bib_content: str) -> list[BibEntry]:
    """Parse raw BibTeX content into a list of :class:`BibEntry` objects."""
    try:
        import bibtexparser  # type: ignore[import-untyped]

        entries: list[BibEntry] = []

        if hasattr(bibtexparser, "loads"):
            # bibtexparser v1.x API
            database = bibtexparser.loads(bib_content)
            for raw_entry in database.entries:
                entry_type = raw_entry.get("ENTRYTYPE", "misc")
                key = raw_entry.get("ID", "unknown")
                fields: dict[str, str] = {
                    k: str(v)
                    for k, v in raw_entry.items()
                    if k not in ("ENTRYTYPE", "ID")
                }
                entries.append(
                    BibEntry(
                        key=key,
                        entry_type=entry_type,
                        fields=fields,
                        status=EntryStatus.unverified,
                    )
                )
        else:
            # bibtexparser v2.x API
            library = bibtexparser.parse_string(bib_content)
            for raw_entry in library.entries:
                entry_type = raw_entry.entry_type
                key = raw_entry.key
                fields = {
                    k: str(v.value)
                    for k, v in raw_entry.fields_dict.items()
                }
                entries.append(
                    BibEntry(
                        key=key,
                        entry_type=entry_type,
                        fields=fields,
                        status=EntryStatus.unverified,
                    )
                )

        return entries
    except Exception as exc:
        logger.error("BibTeX parsing failed: %s", exc)
        return _parse_bibtex_fallback(bib_content)


def _parse_bibtex_fallback(bib_content: str) -> list[BibEntry]:
    """Minimal regex-based fallback parser for simple BibTeX entries."""
    entries: list[BibEntry] = []
    entry_pattern = re.compile(
        r"@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\}", re.DOTALL | re.IGNORECASE
    )
    field_pattern = re.compile(r"\s*(\w+)\s*=\s*[{\"](.*?)[}\"]", re.DOTALL)

    for m in entry_pattern.finditer(bib_content):
        entry_type, key, body = m.group(1), m.group(2), m.group(3)
        fields: dict[str, str] = {}
        for fm in field_pattern.finditer(body):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries.append(
            BibEntry(
                key=key,
                entry_type=entry_type.lower(),
                fields=fields,
                status=EntryStatus.unverified,
            )
        )
    return entries


# ---------------------------------------------------------------------------
# Similarity scoring
# ---------------------------------------------------------------------------

def compute_similarity(a: str, b: str) -> float:
    """Return a similarity ratio in [0.0, 1.0] using RapidFuzz token sort."""
    score: float = fuzz.token_sort_ratio(
        _strip_latex(a).lower(), _strip_latex(b).lower()
    )
    return score / 100.0


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def detect_duplicates(entries: list[BibEntry]) -> list[BibEntry]:
    """Mark entries that share >85 % title similarity as DUPLICATE.

    When a duplicate is found the entry with *fewer* fields is marked as the
    duplicate (keeping the richer record).
    """
    for i, entry_a in enumerate(entries):
        if entry_a.status == EntryStatus.duplicate:
            continue
        title_a = entry_a.fields.get("title", "")
        for j, entry_b in enumerate(entries):
            if i >= j:
                continue
            if entry_b.status == EntryStatus.duplicate:
                continue
            title_b = entry_b.fields.get("title", "")
            score = compute_similarity(title_a, title_b)
            if score * 100 >= DUPLICATE_THRESHOLD:
                # Mark the one with fewer fields as the duplicate
                if len(entry_a.fields) >= len(entry_b.fields):
                    duplicate, canonical = entry_b, entry_a
                else:
                    duplicate, canonical = entry_a, entry_b
                duplicate.status = EntryStatus.duplicate
                duplicate.duplicate_info = DuplicateInfo(
                    duplicate_of_key=canonical.key,
                    similarity_score=score,
                )
    return entries


# ---------------------------------------------------------------------------
# API-based validation
# ---------------------------------------------------------------------------

async def _validate_entry(entry: BibEntry) -> BibEntry:
    """Query ArXiv, DBLP, and Scholar for a single entry and populate matches & suggestions."""
    title = entry.fields.get("title", "")
    year = entry.fields.get("year", "")
    arxiv_id = entry.fields.get("arxiv_id") or entry.fields.get("eprint", "")

    suggestions: list[FieldSuggestion] = []
    api_matches: list[ApiMatch] = []

    # --- ArXiv ---
    try:
        if arxiv_id:
            arxiv_results = [r for r in [await arxiv_client.search_by_id(arxiv_id)] if r]
        elif title:
            arxiv_results = await arxiv_client.search_by_title(title, max_results=3)
        else:
            arxiv_results = []

        logger.info(
            "ArXiv returned %d result(s) for entry '%s'",
            len(arxiv_results),
            entry.key,
        )

        for idx, result in enumerate(arxiv_results):
            source_title = result.get("title", "")
            confidence = compute_similarity(title, source_title) if title and source_title else 0.0
            authors = result.get("authors", [])
            match = ApiMatch(
                source="arxiv",
                title=source_title,
                authors=authors if isinstance(authors, list) else [authors],
                year=result.get("year", ""),
                venue="",
                confidence=confidence,
                fields={
                    "title": source_title,
                    "authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
                    "year": result.get("year", ""),
                    "arxiv_id": result.get("arxiv_id", ""),
                },
            )
            api_matches.append(match)

            # Generate suggestion from the first ArXiv match only
            if idx == 0 and source_title and confidence < 1.0:
                suggestions.append(
                    FieldSuggestion(
                        field_name="title",
                        original_value=title,
                        suggested_value=source_title,
                        confidence=confidence,
                        source="arxiv",
                    )
                )
    except Exception as exc:
        logger.warning("ArXiv validation error for key %s: %s", entry.key, exc)

    # --- DBLP ---
    try:
        if title:
            dblp_results = await dblp_client.search_by_title_and_year(
                title, year=year, max_results=3
            )
        else:
            dblp_results = []

        logger.info(
            "DBLP returned %d result(s) for entry '%s'",
            len(dblp_results),
            entry.key,
        )

        for idx, result in enumerate(dblp_results):
            source_title = result.get("title", "")
            confidence = compute_similarity(title, source_title) if title and source_title else 0.0
            authors = result.get("authors", [])
            venue = result.get("venue", "")
            match = ApiMatch(
                source="dblp",
                title=source_title,
                authors=authors if isinstance(authors, list) else [authors],
                year=result.get("year", ""),
                venue=venue,
                confidence=confidence,
                fields={
                    "title": source_title,
                    "authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
                    "year": result.get("year", ""),
                    "venue": venue,
                },
            )
            api_matches.append(match)

            # Generate suggestions from best DBLP match
            if idx == 0:
                if source_title and confidence < 1.0:
                    arxiv_title_conf = next(
                        (s.confidence for s in suggestions if s.field_name == "title" and s.source == "arxiv"),
                        0.0,
                    )
                    if arxiv_title_conf == 0.0 or confidence > arxiv_title_conf:
                        suggestions.append(
                            FieldSuggestion(
                                field_name="title",
                                original_value=title,
                                suggested_value=source_title,
                                confidence=confidence,
                                source="dblp",
                            )
                        )
                if venue and "journal" not in entry.fields and "booktitle" not in entry.fields:
                    suggestions.append(
                        FieldSuggestion(
                            field_name="venue",
                            original_value=entry.fields.get("venue", ""),
                            suggested_value=venue,
                            confidence=0.80,
                            source="dblp",
                        )
                    )
    except Exception as exc:
        logger.warning("DBLP validation error for key %s: %s", entry.key, exc)

    # --- Google Scholar ---
    try:
        if title:
            loop = asyncio.get_event_loop()
            scholar_results = await loop.run_in_executor(
                None, scholar_client.search_by_title, title, 3
            )
        else:
            scholar_results = []

        logger.info(
            "Scholar returned %d result(s) for entry '%s'",
            len(scholar_results),
            entry.key,
        )

        for idx, result in enumerate(scholar_results):
            source_title = result.get("title", "")
            confidence = compute_similarity(title, source_title) if title and source_title else 0.0
            authors = result.get("authors", [])
            venue = result.get("venue", "")
            match = ApiMatch(
                source="scholar",
                title=source_title,
                authors=authors if isinstance(authors, list) else [authors],
                year=result.get("year", ""),
                venue=venue,
                confidence=confidence,
                fields={
                    "title": source_title,
                    "authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
                    "year": result.get("year", ""),
                    "venue": venue,
                    "citation_count": str(result.get("citation_count", "")),
                },
            )
            api_matches.append(match)

            # Generate suggestion from best Scholar match
            if idx == 0 and source_title and confidence < 1.0:
                existing_sources = {s.source for s in suggestions if s.field_name == "title"}
                if "scholar" not in existing_sources:
                    suggestions.append(
                        FieldSuggestion(
                            field_name="title",
                            original_value=title,
                            suggested_value=source_title,
                            confidence=confidence,
                            source="scholar",
                        )
                    )
    except Exception as exc:
        logger.warning("Scholar validation error for key %s: %s", entry.key, exc)

    entry.suggestions = suggestions
    entry.api_matches = api_matches

    # Determine status
    high_conf = any(s.confidence >= HIGH_CONFIDENCE_THRESHOLD for s in suggestions)
    if suggestions:
        entry.status = EntryStatus.fixed if high_conf else EntryStatus.unverified
    else:
        entry.status = EntryStatus.valid

    return entry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_bib_content(bib_content: str) -> ParseResponse:
    """Parse raw BibTeX content and return a :class:`ParseResponse`."""
    entries = _parse_bibtex(bib_content)
    entries = detect_duplicates(entries)
    issues = sum(1 for e in entries if e.status != EntryStatus.valid)
    duplicates = sum(1 for e in entries if e.status == EntryStatus.duplicate)
    return ParseResponse(
        entries=entries,
        total=len(entries),
        issues_found=issues,
        duplicates_identified=duplicates,
    )


async def validate_entries(entries: list[BibEntry]) -> ValidateResponse:
    """Validate a list of entries against external APIs concurrently."""
    tasks = [
        _validate_entry(entry)
        for entry in entries
        if entry.status != EntryStatus.duplicate
    ]
    validated = await asyncio.gather(*tasks)

    # Merge back (duplicate entries are unchanged)
    validated_map = {e.key: e for e in validated}
    result_entries = [validated_map.get(e.key, e) for e in entries]

    result_entries = detect_duplicates(result_entries)
    issues = sum(1 for e in result_entries if e.status != EntryStatus.valid)
    duplicates = sum(1 for e in result_entries if e.status == EntryStatus.duplicate)
    return ValidateResponse(
        entries=result_entries,
        total=len(result_entries),
        issues_found=issues,
        duplicates_identified=duplicates,
    )


def export_bib(
    entries: list[BibEntry],
    apply_high_confidence: bool = False,
    confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
) -> tuple[str, int]:
    """Serialize entries back to BibTeX, optionally applying high-confidence fixes.

    Returns
    -------
    tuple[str, int]
        The BibTeX string and the number of applied fixes.
    """
    lines: list[str] = []
    applied_fixes = 0

    for entry in entries:
        fields = dict(entry.fields)

        if apply_high_confidence:
            for suggestion in entry.suggestions:
                if suggestion.confidence >= confidence_threshold:
                    fields[suggestion.field_name] = suggestion.suggested_value
                    applied_fixes += 1

        lines.append(f"@{entry.entry_type}{{{entry.key},")
        for field_name, value in fields.items():
            lines.append(f"  {field_name} = {{{value}}},")
        lines.append("}\n")

    return "\n".join(lines), applied_fixes
