import React, { useState } from "react";
import { CheckCircle, AlertCircle, AlertTriangle, Copy, Search } from "lucide-react";
import type { BibEntry, EntryStatus } from "../types";
import { StatusBadge } from "./ui/StatusBadge";

interface EntryListProps {
  entries: BibEntry[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

const statusIcon: Record<EntryStatus, React.ReactNode> = {
  VALID: <CheckCircle size={16} className="text-green-500 shrink-0" />,
  FIXED: <AlertCircle size={16} className="text-blue-500 shrink-0" />,
  UNVERIFIED: <AlertTriangle size={16} className="text-yellow-500 shrink-0" />,
  DUPLICATE: <Copy size={16} className="text-red-500 shrink-0" />,
};

export const EntryList: React.FC<EntryListProps> = ({
  entries,
  selectedKey,
  onSelect,
}) => {
  const [search, setSearch] = useState("");

  const filtered = entries.filter((e) => {
    const q = search.toLowerCase();
    const title = (e.fields.title ?? "").toLowerCase();
    return e.key.toLowerCase().includes(q) || title.includes(q);
  });

  return (
    <aside className="w-72 shrink-0 border-r border-gray-200 bg-white flex flex-col">
      <div className="p-3 border-b border-gray-100">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            placeholder="Search entries…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
        </div>
      </div>

      <ul className="flex-1 overflow-y-auto divide-y divide-gray-100">
        {filtered.length === 0 && (
          <li className="p-4 text-sm text-gray-400 text-center">
            No entries found.
          </li>
        )}
        {filtered.map((entry) => (
          <li
            key={entry.key}
            onClick={() => onSelect(entry.key)}
            className={`p-3 cursor-pointer hover:bg-gray-50 transition-colors ${
              selectedKey === entry.key ? "bg-blue-50 border-l-2 border-blue-500" : ""
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5">{statusIcon[entry.status]}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {entry.key}
                </p>
                <p className="text-xs text-gray-500 truncate mt-0.5">
                  {entry.fields.title ?? "(no title)"}
                </p>
                <div className="mt-1">
                  <StatusBadge status={entry.status} />
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
};
