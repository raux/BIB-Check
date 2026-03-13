# Agent Skills: Bibliography Validation

---
name: bib-parsing
description: Extracts structured data from raw BibTeX strings or files.
---
### Implementation Detail
- Use `bibtexparser.v2`. 
- **Task:** Handle non-standard entries and LaTeX special characters (e.g., `{\"o}`).
- **Outcome:** A JSON list of entry dictionaries.

---
name: cross-reference-validator
description: Queries external APIs to verify entry accuracy.
---
### Implementation Detail
- **ArXiv:** Search by ID if present, else by Title.
- **DBLP:** Search by Title + Year. Prefer DBLP for CS venues.
- **Google Scholar:** Use for citation counts and broad venue validation.
- **Task:** Return a "Confidence Report" comparing `local_title` vs `source_title`.

---
name: similarity-matching
description: Identifies duplicate or near-duplicate references.
---
### Implementation Detail
- Use fuzzy string matching on Titles.
- **Threshold:** Flag items with >85% similarity as "Potential Duplicates."
- **Task:** Provide a merge recommendation (keeping the one with more metadata).

---
name: ui-interactivity
description: Manages the frontend workflow for reviewing and fixing entries.
---
### Implementation Detail
- **Upload:** Drag-and-drop `.bib` file component.
- **Diff View:** Side-by-side comparison of "Current" vs "Validated" fields.
- **Status Badges:** `VALID`, `FIXED`, `UNVERIFIED`, `DUPLICATE`.
- **Export:** Generate a cleaned `.bib` file for download.
