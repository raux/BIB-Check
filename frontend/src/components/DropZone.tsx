import React, { useCallback, useState } from "react";
import { Upload } from "lucide-react";

interface DropZoneProps {
  onFile: (file: File) => void;
  onText: (text: string) => void;
  onDoi: (input: string) => void;
}

export const DropZone: React.FC<DropZoneProps> = ({ onFile, onText, onDoi }) => {
  const [dragging, setDragging] = useState(false);
  const [pasteMode, setPasteMode] = useState(false);
  const [doiMode, setDoiMode] = useState(false);
  const [textValue, setTextValue] = useState("");
  const [doiValue, setDoiValue] = useState("");

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`w-full max-w-lg border-2 border-dashed rounded-xl p-12 flex flex-col items-center gap-4 transition-colors cursor-pointer ${
          dragging
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-blue-300 hover:bg-gray-50"
        }`}
      >
        <Upload size={40} className="text-gray-400" />
        <div className="text-center">
          <p className="text-base font-medium text-gray-700">
            Drag &amp; drop a <code>.bib</code> file here
          </p>
          <p className="text-sm text-gray-400 mt-1">or</p>
        </div>
        <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          Browse file
          <input
            type="file"
            accept=".bib"
            className="hidden"
            onChange={handleFileInput}
          />
        </label>
      </div>

      <div className="w-full max-w-lg">
        <button
          onClick={() => setPasteMode((p) => !p)}
          className="text-sm text-blue-600 hover:underline mb-2"
        >
          {pasteMode ? "Hide" : "Or paste BibTeX directly"}
        </button>
        {pasteMode && (
          <div className="flex flex-col gap-2">
            <textarea
              rows={8}
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              placeholder="@article{key, title={...}, ...}"
              className="w-full border border-gray-200 rounded-lg p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <button
              onClick={() => {
                if (textValue.trim()) onText(textValue);
              }}
              disabled={!textValue.trim()}
              className="self-end bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Parse BibTeX
            </button>
          </div>
        )}
      </div>

      <div className="w-full max-w-lg">
        <button
          onClick={() => setDoiMode((p) => !p)}
          className="text-sm text-blue-600 hover:underline mb-2"
        >
          {doiMode ? "Hide" : "Or enter a DOI / DOI link"}
        </button>
        {doiMode && (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              value={doiValue}
              onChange={(e) => setDoiValue(e.target.value)}
              placeholder="10.1145/1234567 or https://doi.org/10.1145/1234567"
              className="w-full border border-gray-200 rounded-lg p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <button
              onClick={() => {
                if (doiValue.trim()) onDoi(doiValue);
              }}
              disabled={!doiValue.trim()}
              className="self-end bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Fetch BibTeX
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
