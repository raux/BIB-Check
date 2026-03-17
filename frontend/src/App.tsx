import React, { useState, useCallback } from "react";
import { DashboardHeader } from "./components/DashboardHeader";
import { EntryList } from "./components/EntryList";
import { EntryEditor } from "./components/EntryEditor";
import { DropZone } from "./components/DropZone";
import { LogPanel } from "./components/LogPanel";
import type { BibEntry, FieldSuggestion, LogEntry } from "./types";
import {
  parseBib,
  uploadBibFile,
  validateEntries,
  exportBib,
} from "./api/client";

type AppState = "idle" | "loaded" | "validating" | "validated";

const App: React.FC = () => {
  const [appState, setAppState] = useState<AppState>("idle");
  const [entries, setEntries] = useState<BibEntry[]>([]);
  const [stats, setStats] = useState({ total: 0, issuesFound: 0, duplicatesIdentified: 0 });
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsVisible, setLogsVisible] = useState(false);

  const selectedEntry = entries.find((e) => e.key === selectedKey) ?? null;

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    try {
      const response = await uploadBibFile(file);
      setEntries(response.entries);
      setStats({
        total: response.total,
        issuesFound: response.issuesFound,
        duplicatesIdentified: response.duplicatesIdentified,
      });
      setSelectedKey(response.entries[0]?.key ?? null);
      setAppState("loaded");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const handleText = useCallback(async (text: string) => {
    setError(null);
    try {
      const response = await parseBib(text);
      setEntries(response.entries);
      setStats({
        total: response.total,
        issuesFound: response.issuesFound,
        duplicatesIdentified: response.duplicatesIdentified,
      });
      setSelectedKey(response.entries[0]?.key ?? null);
      setAppState("loaded");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const handleValidate = useCallback(async () => {
    setError(null);
    setAppState("validating");
    try {
      const response = await validateEntries(entries);
      setEntries(response.entries);
      setStats({
        total: response.total,
        issuesFound: response.issuesFound,
        duplicatesIdentified: response.duplicatesIdentified,
      });
      // Collect logs from the validation response
      if (response.logs && response.logs.length > 0) {
        setLogs((prev) => [...prev, ...response.logs]);
        setLogsVisible(true);
      }
      setAppState("validated");
    } catch (e) {
      setError(String(e));
      setAppState("loaded");
    }
  }, [entries]);

  const handleAcceptSuggestion = useCallback(
    (entryKey: string, suggestion: FieldSuggestion) => {
      setEntries((prev) =>
        prev.map((e) => {
          if (e.key !== entryKey) return e;
          return {
            ...e,
            fields: { ...e.fields, [suggestion.fieldName]: suggestion.suggestedValue },
            status: "FIXED",
          };
        })
      );
    },
    []
  );

  const handleExport = useCallback(
    async (applyAll: boolean) => {
      setIsExporting(true);
      setError(null);
      try {
        const response = await exportBib(entries, applyAll);
        const blob = new Blob([response.bibContent], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "cleaned.bib";
        a.click();
        URL.revokeObjectURL(url);
      } catch (e) {
        setError(String(e));
      } finally {
        setIsExporting(false);
      }
    },
    [entries]
  );

  const handleReset = () => {
    setAppState("idle");
    setEntries([]);
    setSelectedKey(null);
    setError(null);
    setLogs([]);
    setStats({ total: 0, issuesFound: 0, duplicatesIdentified: 0 });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans">
      <DashboardHeader
        total={stats.total}
        issuesFound={stats.issuesFound}
        duplicatesIdentified={stats.duplicatesIdentified}
      />

      {error && (
        <div className="mx-4 mt-2 px-4 py-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {appState === "idle" ? (
        <main className="flex-1 overflow-hidden">
          <DropZone onFile={handleFile} onText={handleText} />
        </main>
      ) : (
        <main className="flex flex-1 overflow-hidden">
          {/* Left sidebar */}
          <EntryList
            entries={entries}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
          />

          {/* Main panel */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white">
            {selectedEntry ? (
              <EntryEditor
                key={selectedEntry.key}
                entry={selectedEntry}
                onAcceptSuggestion={handleAcceptSuggestion}
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
                Select an entry from the list.
              </div>
            )}

            {/* Bottom bar */}
            <div className="border-t border-gray-200 bg-gray-50 px-4 py-3 flex items-center justify-between gap-3">
              <button
                onClick={handleReset}
                className="text-sm text-gray-500 hover:text-gray-700 underline"
              >
                Load new file
              </button>

              <div className="flex items-center gap-2">
                {appState !== "validated" && (
                  <button
                    onClick={handleValidate}
                    disabled={appState === "validating"}
                    className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                  >
                    {appState === "validating" ? "Validating…" : "Validate via API"}
                  </button>
                )}

                <button
                  onClick={() => handleExport(false)}
                  disabled={isExporting}
                  className="bg-gray-700 hover:bg-gray-800 disabled:bg-gray-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  Export Cleaned BibTeX
                </button>

                <button
                  onClick={() => handleExport(true)}
                  disabled={isExporting}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  Bulk Apply High-Confidence Fixes
                </button>
              </div>
            </div>
          </div>
        </main>
      )}

      {/* Backend log panel — always rendered at the bottom */}
      <LogPanel
        logs={logs}
        visible={logsVisible}
        onToggle={() => setLogsVisible((v) => !v)}
      />
    </div>
  );
};

export default App;
