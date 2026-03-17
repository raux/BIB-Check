"""Pydantic schemas for BibValidate-AI API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class EntryStatus(str, Enum):
    valid = "VALID"
    fixed = "FIXED"
    unverified = "UNVERIFIED"
    duplicate = "DUPLICATE"


class FieldSuggestion(BaseModel):
    field_name: str
    original_value: str
    suggested_value: str
    confidence: float  # 0.0 – 1.0
    source: str  # "arxiv" | "dblp" | "scholar"


class ApiMatch(BaseModel):
    """A full match returned by an external API (ArXiv / DBLP / Scholar)."""

    source: str  # "arxiv" | "dblp" | "scholar"
    title: str = ""
    authors: list[str] = []
    year: str = ""
    venue: str = ""
    confidence: float = 0.0  # title similarity score
    fields: dict[str, str] = {}


class DuplicateInfo(BaseModel):
    duplicate_of_key: str
    similarity_score: float  # 0.0 – 1.0


class LogEntry(BaseModel):
    """A single backend log message."""

    level: str  # "INFO" | "WARNING" | "ERROR" | "DEBUG"
    message: str
    timestamp: str  # ISO-8601


class BibEntry(BaseModel):
    key: str
    entry_type: str
    fields: dict[str, str]
    status: EntryStatus = EntryStatus.unverified
    suggestions: list[FieldSuggestion] = []
    api_matches: list[ApiMatch] = []
    duplicate_info: DuplicateInfo | None = None


class ParseRequest(BaseModel):
    bib_content: str


class ParseResponse(BaseModel):
    entries: list[BibEntry]
    total: int
    issues_found: int
    duplicates_identified: int


class ValidateRequest(BaseModel):
    entries: list[BibEntry]


class ValidateResponse(BaseModel):
    entries: list[BibEntry]
    total: int
    issues_found: int
    duplicates_identified: int
    logs: list[LogEntry] = []


class ExportRequest(BaseModel):
    entries: list[BibEntry]
    apply_high_confidence: bool = False
    confidence_threshold: float = 0.95


class ExportResponse(BaseModel):
    bib_content: str
    applied_fixes: int
