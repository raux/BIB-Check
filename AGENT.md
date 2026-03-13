# Agent Profile: BibValidate-AI

## Project Overview
BibValidate-AI is a high-precision tool designed to validate, cross-reference, and fix BibTeX entries. It interfaces with ArXiv, DBLP, and Google Scholar to ensure that titles, authors, and venues are accurate and match official records.

## Tech Stack
- **Backend:** Python 3.10+, FastAPI
- **Parsing:** `bibtexparser` (v2) for robust BibTeX handling
- **Frontend:** React + Vite, TailwindCSS (Shadcn/UI for components)
- **APIs:** 
  - ArXiv API (via `arxiv` python wrapper)
  - DBLP Search API (REST/JSON)
  - Google Scholar (via `scholarly` or SerpApi)
- **Similarity Logic:** `RapidFuzz` or `Levenshtein` for title/author fuzzy matching.

## Architecture Guidelines
- **Modularity:** Keep API clients in `backend/services/`.
- **Validation Engine:** Logic for "similarity scoring" resides in `backend/core/validator.py`.
- **Data Flow:** Bib file -> Parser -> Metadata Enhancement -> Similarity Check -> UI Correction -> Export.

## Operational Rules
1. **API Rate Limiting:** Always implement exponential backoff for ArXiv and DBLP. 
2. **Data Integrity:** Never overwrite a user's original BibTeX field unless the confidence score is >95%. Store "suggested" changes separately for UI review.
3. **Naming Convention:** Use `camelCase` for frontend and `snake_case` for backend.
4. **Mocking:** Use `pytest` with `unittest.mock` for API responses to avoid hitting live endpoints during CI.

## Communication
- For new UI features, refer to the design system in `frontend/src/components/ui/`.
- For logic changes, update the relevant Skill in `SKILLS.md`.
