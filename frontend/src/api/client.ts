/**
 * API client for the BibValidate-AI backend.
 * All camelCase response fields correspond to snake_case in the API (handled by key transforms).
 */

import type {
  BibEntry,
  ExportResponse,
  LogEntry,
  ParseResponse,
  ValidateResponse,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Recursively converts snake_case keys to camelCase. */
function toCamel(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toCamel);
  if (obj !== null && typeof obj === "object") {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase()),
        toCamel(v),
      ])
    );
  }
  return obj;
}

/** Recursively converts camelCase keys to snake_case. */
function toSnake(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toSnake);
  if (obj !== null && typeof obj === "object") {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        k.replace(/([A-Z])/g, (_: string, c: string) => `_${c.toLowerCase()}`),
        toSnake(v),
      ])
    );
  }
  return obj;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toSnake(body)),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  const json = await res.json();
  return toCamel(json) as T;
}

export async function parseBib(bibContent: string): Promise<ParseResponse> {
  return post<ParseResponse>("/parse", { bibContent });
}

export async function uploadBibFile(file: File): Promise<ParseResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/parse/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  const json = await res.json();
  return toCamel(json) as ParseResponse;
}

export async function validateEntries(entries: BibEntry[]): Promise<ValidateResponse> {
  return post<ValidateResponse>("/validate", { entries });
}

export async function exportBib(
  entries: BibEntry[],
  applyHighConfidence = false,
  confidenceThreshold = 0.95
): Promise<ExportResponse> {
  return post<ExportResponse>("/export", {
    entries,
    applyHighConfidence,
    confidenceThreshold,
  });
}

export async function fetchLogs(): Promise<LogEntry[]> {
  const res = await fetch(`${BASE_URL}/logs`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  const json = await res.json();
  return toCamel(json) as LogEntry[];
}
