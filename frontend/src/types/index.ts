export type EntryStatus = "VALID" | "FIXED" | "UNVERIFIED" | "DUPLICATE";

export interface FieldSuggestion {
  fieldName: string;
  originalValue: string;
  suggestedValue: string;
  confidence: number; // 0.0 – 1.0
  source: "arxiv" | "dblp" | "scholar";
}

export interface DuplicateInfo {
  duplicateOfKey: string;
  similarityScore: number;
}

export interface BibEntry {
  key: string;
  entryType: string;
  fields: Record<string, string>;
  status: EntryStatus;
  suggestions: FieldSuggestion[];
  duplicateInfo?: DuplicateInfo | null;
}

export interface ParseResponse {
  entries: BibEntry[];
  total: number;
  issuesFound: number;
  duplicatesIdentified: number;
}

export interface ValidateResponse {
  entries: BibEntry[];
  total: number;
  issuesFound: number;
  duplicatesIdentified: number;
}

export interface ExportResponse {
  bibContent: string;
  appliedFixes: number;
}
