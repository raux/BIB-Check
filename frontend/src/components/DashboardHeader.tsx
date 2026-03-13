import React from "react";
import { BookOpen, AlertTriangle, Copy } from "lucide-react";

interface DashboardHeaderProps {
  total: number;
  issuesFound: number;
  duplicatesIdentified: number;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  total,
  issuesFound,
  duplicatesIdentified,
}) => {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">BibValidate-AI</h1>
        <p className="text-sm text-gray-500">
          High-precision BibTeX validation &amp; correction
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard
          icon={<BookOpen className="text-blue-500" size={20} />}
          label="Total References"
          value={total}
          bgColor="bg-blue-50"
        />
        <StatCard
          icon={<AlertTriangle className="text-yellow-500" size={20} />}
          label="Issues Found"
          value={issuesFound}
          bgColor="bg-yellow-50"
        />
        <StatCard
          icon={<Copy className="text-red-500" size={20} />}
          label="Duplicates Identified"
          value={duplicatesIdentified}
          bgColor="bg-red-50"
        />
      </div>
    </header>
  );
};

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  bgColor: string;
}

const StatCard: React.FC<StatCardProps> = ({ icon, label, value, bgColor }) => (
  <div className={`rounded-lg ${bgColor} p-3 flex items-center gap-3`}>
    {icon}
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-xl font-semibold text-gray-800">{value}</p>
    </div>
  </div>
);
