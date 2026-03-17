import React, { useRef, useEffect } from "react";
import { Terminal } from "lucide-react";
import type { LogEntry } from "../types";

interface LogPanelProps {
  logs: LogEntry[];
  visible: boolean;
  onToggle: () => void;
}

const levelColor: Record<string, string> = {
  DEBUG: "text-gray-400",
  INFO: "text-blue-400",
  WARNING: "text-yellow-400",
  ERROR: "text-red-400",
};

export const LogPanel: React.FC<LogPanelProps> = ({
  logs,
  visible,
  onToggle,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (visible && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, visible]);

  return (
    <div className="border-t border-gray-300 bg-gray-900 flex flex-col">
      {/* Toggle bar */}
      <button
        onClick={onToggle}
        className="flex items-center gap-2 px-4 py-1.5 text-xs text-gray-300 hover:bg-gray-800 transition-colors"
      >
        <Terminal size={14} />
        <span className="font-semibold">Backend Logs</span>
        {logs.length > 0 && (
          <span className="ml-1 bg-gray-700 text-gray-300 rounded px-1.5 py-0.5 text-[10px] font-mono">
            {logs.length}
          </span>
        )}
        <span className="ml-auto text-gray-500">
          {visible ? "▼ Hide" : "▲ Show"}
        </span>
      </button>

      {visible && (
        <div className="max-h-48 overflow-y-auto px-4 py-2 font-mono text-xs leading-relaxed">
          {logs.length === 0 ? (
            <p className="text-gray-500 text-center py-4">
              No logs yet. Run a validation to see backend output.
            </p>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex gap-2 py-0.5">
                <span className="text-gray-600 shrink-0 w-20 text-right">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span
                  className={`shrink-0 w-16 font-bold ${levelColor[log.level] ?? "text-gray-300"}`}
                >
                  {log.level}
                </span>
                <span className="text-gray-300 break-all">{log.message}</span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
};
