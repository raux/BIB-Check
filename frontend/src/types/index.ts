export type EntryStatus = "VALID" | "FIXED" | "UNVERIFIED" | "DUPLICATE";

export interface FieldSuggestion {
  fieldName: string;
  originalValue: string;
  suggestedValue: string;
  confidence: number; // 0.0 – 1.0
  source: "arxiv" | "dblp" | "scholar";
}

export interface ApiMatch {
  source: "arxiv" | "dblp" | "scholar";
  title: string;
  authors: string[];
  year: string;
  venue: string;
  confidence: number; // 0.0 – 1.0
  fields: Record<string, string>;
}

export interface DuplicateInfo {
  duplicateOfKey: string;
  similarityScore: number;
}

export interface LogEntry {
  level: string;
  message: string;
  timestamp: string;
}

export interface BibEntry {
  key: string;
  entryType: string;
  fields: Record<string, string>;
  status: EntryStatus;
  suggestions: FieldSuggestion[];
  apiMatches: ApiMatch[];
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
  logs: LogEntry[];
}

export interface ExportResponse {
  bibContent: string;
  appliedFixes: number;
}

export interface Doi2BibRequest {
  input: string;
}
