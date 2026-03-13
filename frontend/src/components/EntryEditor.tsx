import React, { useState } from "react";
import type { BibEntry, FieldSuggestion } from "../types";
import { StatusBadge } from "./ui/StatusBadge";
import { SimilarityBar } from "./ui/SimilarityBar";

interface EntryEditorProps {
  entry: BibEntry;
  onAcceptSuggestion: (entryKey: string, suggestion: FieldSuggestion) => void;
}

export const EntryEditor: React.FC<EntryEditorProps> = ({
  entry,
  onAcceptSuggestion,
}) => {
  const [accepted, setAccepted] = useState<Set<string>>(new Set());

  const handleToggle = (suggestion: FieldSuggestion) => {
    const id = `${suggestion.fieldName}:${suggestion.source}`;
    setAccepted((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        onAcceptSuggestion(entry.key, suggestion);
      }
      return next;
    });
  };

  // Build comparison rows: all fields + any suggestion fields not already present
  const suggestionMap: Record<string, FieldSuggestion[]> = {};
  for (const s of entry.suggestions) {
    if (!suggestionMap[s.fieldName]) suggestionMap[s.fieldName] = [];
    suggestionMap[s.fieldName].push(s);
  }

  const allFieldNames = Array.from(
    new Set([...Object.keys(entry.fields), ...Object.keys(suggestionMap)])
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">{entry.key}</h2>
          <p className="text-xs text-gray-500">
            @{entry.entryType}
            {entry.duplicateInfo && (
              <span className="ml-2 text-red-500">
                Duplicate of <strong>{entry.duplicateInfo.duplicateOfKey}</strong> (
                {Math.round(entry.duplicateInfo.similarityScore * 100)}% match)
              </span>
            )}
          </p>
        </div>
        <StatusBadge status={entry.status} />
      </div>

      {/* Original BibTeX source */}
      <div className="px-4 py-3 border-b border-gray-200">
        <p className="text-xs font-semibold text-gray-500 uppercase mb-1">
          Original BibTeX
        </p>
        <pre className="text-xs bg-gray-100 rounded p-3 overflow-x-auto whitespace-pre-wrap text-gray-700 font-mono">
          {serializeEntry(entry)}
        </pre>
      </div>

      {/* Comparison table */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
          Field Comparison
        </p>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-xs text-gray-500 border-b border-gray-200">
              <th className="text-left pb-2 w-28">Field</th>
              <th className="text-left pb-2">Original Value</th>
              <th className="text-left pb-2">Validated Value (API)</th>
              <th className="text-left pb-2 w-24">Confidence</th>
              <th className="text-left pb-2 w-16">Accept</th>
            </tr>
          </thead>
          <tbody>
            {allFieldNames.map((fieldName) => {
              const original = entry.fields[fieldName] ?? "";
              const suggestions = suggestionMap[fieldName] ?? [];
              const topSuggestion = suggestions[0];

              if (!topSuggestion) {
                return (
                  <tr key={fieldName} className="border-b border-gray-100">
                    <td className="py-2 pr-2 font-mono text-xs text-gray-500 align-top">
                      {fieldName}
                    </td>
                    <td className="py-2 pr-2 text-gray-800 align-top" colSpan={3}>
                      {original}
                    </td>
                    <td />
                  </tr>
                );
              }

              const id = `${topSuggestion.fieldName}:${topSuggestion.source}`;
              const isAccepted = accepted.has(id);

              return (
                <tr
                  key={fieldName}
                  className="border-b border-gray-100 bg-yellow-50"
                >
                  <td className="py-2 pr-2 font-mono text-xs text-gray-500 align-top">
                    {fieldName}
                  </td>
                  <td className="py-2 pr-2 text-gray-600 align-top line-through decoration-red-400">
                    {original}
                  </td>
                  <td className="py-2 pr-2 text-gray-800 font-medium align-top">
                    <span>{topSuggestion.suggestedValue}</span>
                    <span className="ml-1 text-xs text-gray-400">
                      via {topSuggestion.source}
                    </span>
                  </td>
                  <td className="py-2 pr-2 align-top">
                    <SimilarityBar value={topSuggestion.confidence} />
                  </td>
                  <td className="py-2 align-top">
                    <button
                      onClick={() => handleToggle(topSuggestion)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        isAccepted ? "bg-blue-500" : "bg-gray-300"
                      }`}
                      aria-label={`${isAccepted ? "Reject" : "Accept"} suggestion for ${fieldName}`}
                    >
                      <span
                        className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                          isAccepted ? "translate-x-4" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {entry.suggestions.length === 0 && (
          <p className="text-sm text-gray-400 mt-4 text-center">
            No suggestions for this entry.
          </p>
        )}
      </div>
    </div>
  );
};

function serializeEntry(entry: BibEntry): string {
  const lines = [`@${entry.entryType}{${entry.key},`];
  for (const [k, v] of Object.entries(entry.fields)) {
    lines.push(`  ${k} = {${v}},`);
  }
  lines.push("}");
  return lines.join("\n");
}
