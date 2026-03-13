"""Core validation engine for BibValidate-AI.

Responsibilities
----------------
1. Parse a raw BibTeX string into :class:`BibEntry` objects.
2. Query ArXiv / DBLP / Scholar for each entry and produce
   :class:`FieldSuggestion` objects.
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

from ..models.schemas import (
    BibEntry,
    DuplicateInfo,
    EntryStatus,
    FieldSuggestion,
    ParseResponse,
    ValidateResponse,
)
from ..services import arxiv_client, dblp_client

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

        library = bibtexparser.parse_string(bib_content)
        entries: list[BibEntry] = []
        for raw_entry in library.entries:
            fields: dict[str, str] = {}
            for field in raw_entry.fields:
                fields[field.key] = str(field.value)
            entries.append(
                BibEntry(
                    key=raw_entry.key,
                    entry_type=raw_entry.entry_type,
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
    """Query ArXiv and DBLP for a single entry and populate suggestions."""
    title = entry.fields.get("title", "")
    year = entry.fields.get("year", "")
    arxiv_id = entry.fields.get("arxiv_id") or entry.fields.get("eprint", "")

    suggestions: list[FieldSuggestion] = []

    # --- ArXiv ---
    try:
        if arxiv_id:
            arxiv_results = [r for r in [await arxiv_client.search_by_id(arxiv_id)] if r]
        elif title:
            arxiv_results = await arxiv_client.search_by_title(title, max_results=1)
        else:
            arxiv_results = []

        for result in arxiv_results[:1]:
            source_title = result.get("title", "")
            if source_title:
                confidence = compute_similarity(title, source_title)
                if confidence < 1.0:
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
                title, year=year, max_results=1
            )
            for result in dblp_results[:1]:
                source_title = result.get("title", "")
                if source_title:
                    confidence = compute_similarity(title, source_title)
                    if confidence < 1.0:
                        # Only add if different from arxiv suggestion
                        already = any(
                            s.field_name == "title" and s.source == "arxiv"
                            for s in suggestions
                        )
                        if not already or confidence > (
                            suggestions[0].confidence if suggestions else 0
                        ):
                            suggestions.append(
                                FieldSuggestion(
                                    field_name="title",
                                    original_value=title,
                                    suggested_value=source_title,
                                    confidence=confidence,
                                    source="dblp",
                                )
                            )
                venue = result.get("venue", "")
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

    entry.suggestions = suggestions

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
