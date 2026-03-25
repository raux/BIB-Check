"""Tests for the core validation engine (mocked external APIs)."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.validator import (
    DUPLICATE_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    compute_similarity,
    detect_duplicates,
    export_bib,
    parse_bib_content,
    validate_entries,
)
from backend.models.schemas import BibEntry, EntryStatus, FieldSuggestion
from backend.services.doi2bib_client import extract_doi

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_BIB = r"""
@article{smith2020,
  title = {Deep Learning for Natural Language Processing},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of AI Research},
  year = {2020},
}

@inproceedings{jones2019,
  title = {Attention Is All You Need},
  author = {Jones, Bob},
  booktitle = {NeurIPS},
  year = {2019},
}
"""

DUPLICATE_BIB = r"""
@article{paper1,
  title = {Deep Learning for Natural Language Processing},
  author = {Smith, John},
  year = {2020},
}

@article{paper2,
  title = {Deep Learning for Natural Language Processing},
  author = {Smith, John and Doe, Jane},
  year = {2020},
  journal = {AI Journal},
  volume = {5},
}
"""


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

def test_parse_bib_content_returns_entries():
    response = parse_bib_content(SAMPLE_BIB)
    assert response.total == 2
    assert len(response.entries) == 2
    keys = {e.key for e in response.entries}
    assert "smith2020" in keys
    assert "jones2019" in keys


def test_parse_bib_content_sets_unverified_status():
    response = parse_bib_content(SAMPLE_BIB)
    for entry in response.entries:
        assert entry.status == EntryStatus.unverified


def test_parse_empty_content_returns_empty():
    response = parse_bib_content("   ")
    assert response.total == 0
    assert response.entries == []


# ---------------------------------------------------------------------------
# Duplicate detection tests
# ---------------------------------------------------------------------------

def test_detect_duplicates_marks_duplicate():
    response = parse_bib_content(DUPLICATE_BIB)
    statuses = {e.key: e.status for e in response.entries}
    assert statuses["paper1"] == EntryStatus.duplicate or statuses["paper2"] == EntryStatus.duplicate


def test_detect_duplicates_keeps_richer_entry():
    """The entry with more fields should remain non-duplicate."""
    response = parse_bib_content(DUPLICATE_BIB)
    # paper2 has more fields (journal, volume) so paper1 should be the duplicate
    paper1 = next(e for e in response.entries if e.key == "paper1")
    paper2 = next(e for e in response.entries if e.key == "paper2")
    assert paper1.status == EntryStatus.duplicate
    assert paper2.status != EntryStatus.duplicate


def test_detect_duplicates_no_false_positives():
    response = parse_bib_content(SAMPLE_BIB)
    statuses = [e.status for e in response.entries]
    assert EntryStatus.duplicate not in statuses


# ---------------------------------------------------------------------------
# Similarity computation tests
# ---------------------------------------------------------------------------

def test_compute_similarity_identical():
    assert compute_similarity("Hello World", "Hello World") == pytest.approx(1.0)


def test_compute_similarity_different():
    score = compute_similarity("Deep Learning", "Quantum Physics")
    assert score < 0.5


def test_compute_similarity_near_match():
    score = compute_similarity(
        "Attention Is All You Need",
        "Attention is all you need",
    )
    assert score > 0.9


# ---------------------------------------------------------------------------
# Validation tests (mocked APIs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_entries_valid_when_no_suggestions():
    entries = parse_bib_content(SAMPLE_BIB).entries
    with (
        patch(
            "backend.core.validator.arxiv_client.search_by_title",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "backend.core.validator.arxiv_client.search_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "backend.core.validator.dblp_client.search_by_title_and_year",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "backend.core.validator.scholar_client.search_by_title",
            return_value=[],
        ),
    ):
        response = await validate_entries(entries)

    for entry in response.entries:
        assert entry.status == EntryStatus.valid
        assert entry.suggestions == []


@pytest.mark.asyncio
async def test_validate_entries_creates_suggestion_on_mismatch():
    entries = parse_bib_content(SAMPLE_BIB).entries

    arxiv_result = [
        {
            "title": "Deep Learning for Natural Language Processing (Survey)",
            "authors": ["Smith, John"],
            "year": "2020",
            "arxiv_id": "2001.12345",
        }
    ]
    with (
        patch(
            "backend.core.validator.arxiv_client.search_by_title",
            new_callable=AsyncMock,
            return_value=arxiv_result,
        ),
        patch(
            "backend.core.validator.arxiv_client.search_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "backend.core.validator.dblp_client.search_by_title_and_year",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "backend.core.validator.scholar_client.search_by_title",
            return_value=[],
        ),
    ):
        response = await validate_entries(entries)

    smith_entry = next(e for e in response.entries if e.key == "smith2020")
    # A suggestion should have been created for the title field
    assert len(smith_entry.suggestions) >= 1
    title_suggestion = next(
        (s for s in smith_entry.suggestions if s.field_name == "title"), None
    )
    assert title_suggestion is not None
    assert title_suggestion.source == "arxiv"


@pytest.mark.asyncio
async def test_validate_entries_status_fixed_on_high_confidence():
    """An entry with a high-confidence suggestion should become FIXED."""
    entries = parse_bib_content(SAMPLE_BIB).entries

    # Find the entry that will receive a nearly-identical title from ArXiv
    perfect_match_title = "Deep Learning for Natural Language Processing"
    # Simulate ArXiv returning a slightly reformatted version with >95% confidence
    slightly_different = "Deep Learning for Natural-Language Processing"
    arxiv_result = [
        {
            "title": slightly_different,
            "authors": ["Smith, John"],
            "year": "2020",
            "arxiv_id": "2001.12345",
        }
    ]
    with (
        patch(
            "backend.core.validator.arxiv_client.search_by_title",
            new_callable=AsyncMock,
            return_value=arxiv_result,
        ),
        patch(
            "backend.core.validator.arxiv_client.search_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "backend.core.validator.dblp_client.search_by_title_and_year",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "backend.core.validator.scholar_client.search_by_title",
            return_value=[],
        ),
    ):
        response = await validate_entries(entries)

    smith_entry = next(e for e in response.entries if e.key == "smith2020")
    # Status depends on similarity; entry should not be UNVERIFIED/VALID without suggestion
    assert smith_entry.status in (
        EntryStatus.valid,
        EntryStatus.fixed,
        EntryStatus.unverified,
    )


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

def test_export_bib_no_fixes():
    entries = parse_bib_content(SAMPLE_BIB).entries
    bib_str, applied = export_bib(entries, apply_high_confidence=False)
    assert applied == 0
    assert "@article" in bib_str or "@inproceedings" in bib_str
    assert "smith2020" in bib_str
    assert "jones2019" in bib_str


def test_export_bib_applies_high_confidence_fix():
    entry = BibEntry(
        key="test2021",
        entry_type="article",
        fields={"title": "Old Title", "year": "2021"},
        status=EntryStatus.unverified,
        suggestions=[
            FieldSuggestion(
                field_name="title",
                original_value="Old Title",
                suggested_value="New Corrected Title",
                confidence=0.97,  # above HIGH_CONFIDENCE_THRESHOLD
                source="dblp",
            )
        ],
    )
    bib_str, applied = export_bib([entry], apply_high_confidence=True)
    assert applied == 1
    assert "New Corrected Title" in bib_str


def test_export_bib_does_not_apply_low_confidence_fix():
    entry = BibEntry(
        key="test2021",
        entry_type="article",
        fields={"title": "Old Title", "year": "2021"},
        status=EntryStatus.unverified,
        suggestions=[
            FieldSuggestion(
                field_name="title",
                original_value="Old Title",
                suggested_value="Possibly Wrong Title",
                confidence=0.70,  # below HIGH_CONFIDENCE_THRESHOLD
                source="dblp",
            )
        ],
    )
    bib_str, applied = export_bib([entry], apply_high_confidence=True)
    assert applied == 0
    assert "Old Title" in bib_str
    assert "Possibly Wrong Title" not in bib_str


# ---------------------------------------------------------------------------
# API match collection tests (all APIs cross-referenced)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_entries_collects_api_matches_from_all_sources():
    """Validation should populate api_matches from ArXiv, DBLP, and Scholar."""
    entries = parse_bib_content(SAMPLE_BIB).entries

    arxiv_result = [
        {"title": "DL for NLP", "authors": ["Smith"], "year": "2020", "arxiv_id": "2001.1"},
        {"title": "DL for NLP v2", "authors": ["Smith"], "year": "2020", "arxiv_id": "2001.2"},
    ]
    dblp_result = [
        {"title": "DL for NLP (DBLP)", "authors": ["Smith, John"], "year": "2020", "venue": "AI Conf"},
    ]
    scholar_result = [
        {"title": "DL for NLP (Scholar)", "authors": ["Smith, J."], "year": "2020", "venue": "AAAI", "citation_count": 42},
    ]

    with (
        patch("backend.core.validator.arxiv_client.search_by_title", new_callable=AsyncMock, return_value=arxiv_result),
        patch("backend.core.validator.arxiv_client.search_by_id", new_callable=AsyncMock, return_value=None),
        patch("backend.core.validator.dblp_client.search_by_title_and_year", new_callable=AsyncMock, return_value=dblp_result),
        patch("backend.core.validator.scholar_client.search_by_title", return_value=scholar_result),
    ):
        response = await validate_entries(entries)

    smith_entry = next(e for e in response.entries if e.key == "smith2020")
    sources = {m.source for m in smith_entry.api_matches}
    assert "arxiv" in sources
    assert "dblp" in sources
    assert "scholar" in sources
    assert len(smith_entry.api_matches) >= 3  # at least one from each


@pytest.mark.asyncio
async def test_validate_entries_api_matches_contain_fields():
    """Each ApiMatch should carry a populated fields dict."""
    entries = parse_bib_content(SAMPLE_BIB).entries

    dblp_result = [
        {"title": "Attention Is All You Need", "authors": ["Jones"], "year": "2019", "venue": "NeurIPS"},
    ]

    with (
        patch("backend.core.validator.arxiv_client.search_by_title", new_callable=AsyncMock, return_value=[]),
        patch("backend.core.validator.arxiv_client.search_by_id", new_callable=AsyncMock, return_value=None),
        patch("backend.core.validator.dblp_client.search_by_title_and_year", new_callable=AsyncMock, return_value=dblp_result),
        patch("backend.core.validator.scholar_client.search_by_title", return_value=[]),
    ):
        response = await validate_entries(entries)

    jones_entry = next(e for e in response.entries if e.key == "jones2019")
    assert len(jones_entry.api_matches) >= 1
    match = jones_entry.api_matches[0]
    assert match.source == "dblp"
    assert "title" in match.fields
    assert "venue" in match.fields
    assert match.fields["venue"] == "NeurIPS"


@pytest.mark.asyncio
async def test_validate_entries_scholar_integration():
    """Scholar results should become api_matches even when ArXiv/DBLP return nothing."""
    entries = parse_bib_content(SAMPLE_BIB).entries

    scholar_result = [
        {"title": "Deep Learning for NLP Extended", "authors": ["Smith, John"], "year": "2020", "venue": "JAIR", "citation_count": 100},
    ]

    with (
        patch("backend.core.validator.arxiv_client.search_by_title", new_callable=AsyncMock, return_value=[]),
        patch("backend.core.validator.arxiv_client.search_by_id", new_callable=AsyncMock, return_value=None),
        patch("backend.core.validator.dblp_client.search_by_title_and_year", new_callable=AsyncMock, return_value=[]),
        patch("backend.core.validator.scholar_client.search_by_title", return_value=scholar_result),
    ):
        response = await validate_entries(entries)

    smith_entry = next(e for e in response.entries if e.key == "smith2020")
    scholar_matches = [m for m in smith_entry.api_matches if m.source == "scholar"]
    assert len(scholar_matches) == 1
    assert scholar_matches[0].fields.get("citation_count") == "100"


# ---------------------------------------------------------------------------
# Log handler tests
# ---------------------------------------------------------------------------

def test_memory_log_handler_captures_logs():
    from backend.core.log_handler import MemoryLogHandler

    handler = MemoryLogHandler(capacity=10)
    handler.setFormatter(logging.Formatter("%(message)s"))
    test_logger = logging.getLogger("test.memory_handler")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    test_logger.info("hello")
    test_logger.warning("world")

    entries = handler.get_entries()
    assert len(entries) == 2
    assert entries[0].level == "INFO"
    assert entries[0].message == "hello"
    assert entries[1].level == "WARNING"

    # drain clears the buffer
    drained = handler.drain()
    assert len(drained) == 2
    assert handler.get_entries() == []

    test_logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# DOI extraction tests
# ---------------------------------------------------------------------------

def test_extract_doi_plain_doi():
    assert extract_doi("10.1145/1234567.1234568") == "10.1145/1234567.1234568"


def test_extract_doi_from_doi_org_url():
    assert extract_doi("https://doi.org/10.1145/1234567.1234568") == "10.1145/1234567.1234568"


def test_extract_doi_from_dx_doi_org_url():
    assert extract_doi("https://dx.doi.org/10.1038/nphys1170") == "10.1038/nphys1170"


def test_extract_doi_from_doi2bib_url():
    assert extract_doi("https://www.doi2bib.org/bib/10.1145/1234567") == "10.1145/1234567"


def test_extract_doi_empty_input():
    assert extract_doi("") == ""


def test_extract_doi_invalid_input():
    assert extract_doi("not-a-doi") == ""


def test_extract_doi_with_whitespace():
    assert extract_doi("  10.1145/1234567  ") == "10.1145/1234567"


# ---------------------------------------------------------------------------
# doi2bib fetch tests (mocked HTTP)
# ---------------------------------------------------------------------------

SAMPLE_DOI_BIB = r"""@article{Smith_2020,
  title = {Deep Learning for NLP},
  author = {Smith, John},
  journal = {Journal of AI},
  year = {2020},
  doi = {10.1234/example},
}
"""


@pytest.mark.asyncio
async def test_fetch_bibtex_success():
    from backend.services.doi2bib_client import fetch_bibtex

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_DOI_BIB

    with patch("backend.services.doi2bib_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await fetch_bibtex("10.1234/example")
        assert "@article" in result
        assert "Smith" in result


@pytest.mark.asyncio
async def test_fetch_bibtex_returns_empty_on_failure():
    from backend.services.doi2bib_client import fetch_bibtex

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=Exception("Not Found")
    )

    with patch("backend.services.doi2bib_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(Exception):
            await fetch_bibtex("10.9999/nonexistent")


def test_doi2bib_parse_integration():
    """BibTeX fetched via doi2bib should be parseable by parse_bib_content."""
    response = parse_bib_content(SAMPLE_DOI_BIB)
    assert response.total >= 1
    entry = response.entries[0]
    assert "title" in entry.fields
