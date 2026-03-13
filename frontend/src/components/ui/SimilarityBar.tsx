import React from "react";

interface SimilarityBarProps {
  /** Value between 0.0 and 1.0 */
  value: number;
}

export const SimilarityBar: React.FC<SimilarityBarProps> = ({ value }) => {
  const pct = Math.round(value * 100);
  const color =
    pct >= 95 ? "bg-green-500" : pct >= 75 ? "bg-yellow-400" : "bg-red-400";

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full bg-gray-200 overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-600">{pct}%</span>
    </div>
  );
};
