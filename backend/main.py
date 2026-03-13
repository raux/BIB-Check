"""FastAPI application entry point for BibValidate-AI."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .core import validator
from .models.schemas import (
    ExportRequest,
    ExportResponse,
    ParseRequest,
    ParseResponse,
    ValidateRequest,
    ValidateResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BibValidate-AI",
    description="High-precision BibTeX validation, cross-referencing, and fixing.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse", response_model=ParseResponse)
async def parse_bib(request: ParseRequest) -> ParseResponse:
    """Parse a raw BibTeX string and return structured entries."""
    if not request.bib_content.strip():
        raise HTTPException(status_code=400, detail="bib_content must not be empty.")
    return validator.parse_bib_content(request.bib_content)


@app.post("/parse/upload", response_model=ParseResponse)
async def parse_bib_upload(file: UploadFile) -> ParseResponse:
    """Parse an uploaded .bib file and return structured entries."""
    if not file.filename or not file.filename.endswith(".bib"):
        raise HTTPException(status_code=400, detail="Only .bib files are accepted.")
    content = await file.read()
    bib_content = content.decode("utf-8", errors="replace")
    if not bib_content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return validator.parse_bib_content(bib_content)


@app.post("/validate", response_model=ValidateResponse)
async def validate_entries(request: ValidateRequest) -> ValidateResponse:
    """Validate entries against ArXiv / DBLP / Scholar APIs."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="entries must not be empty.")
    return await validator.validate_entries(request.entries)


@app.post("/export", response_model=ExportResponse)
async def export_bib(request: ExportRequest) -> ExportResponse:
    """Serialize entries back to BibTeX, optionally applying high-confidence fixes."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="entries must not be empty.")
    bib_content, applied_fixes = validator.export_bib(
        request.entries,
        apply_high_confidence=request.apply_high_confidence,
        confidence_threshold=request.confidence_threshold,
    )
    return ExportResponse(bib_content=bib_content, applied_fixes=applied_fixes)
