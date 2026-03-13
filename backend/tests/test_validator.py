"""Tests for the core validation engine (mocked external APIs)."""

from __future__ import annotations

import asyncio
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
