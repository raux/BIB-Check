import React from "react";
import type { EntryStatus } from "../../types";

const config: Record<
  EntryStatus,
  { label: string; className: string }
> = {
  VALID: {
    label: "VALID",
    className: "bg-green-100 text-green-800 border border-green-300",
  },
  FIXED: {
    label: "FIXED",
    className: "bg-blue-100 text-blue-800 border border-blue-300",
  },
  UNVERIFIED: {
    label: "UNVERIFIED",
    className: "bg-yellow-100 text-yellow-800 border border-yellow-300",
  },
  DUPLICATE: {
    label: "DUPLICATE",
    className: "bg-red-100 text-red-800 border border-red-300",
  },
};

interface StatusBadgeProps {
  status: EntryStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const { label, className } = config[status] ?? config.UNVERIFIED;
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${className}`}
    >
      {label}
    </span>
  );
};
