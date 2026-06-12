"use client";

import { useMemo, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { parseVocabImportText, type WordFormInput } from "@/lib/vocab-csv";

export function ImportWordsModal({
  open,
  onClose,
  onImport,
}: {
  open: boolean;
  onClose: () => void;
  onImport: (rows: WordFormInput[]) => void;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parsed = useMemo(() => parseVocabImportText(text), [text]);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") setText(result);
      setError(null);
    };
    reader.onerror = () => setError("Could not read file");
    reader.readAsText(file);
  }

  function handleImport() {
    if (parsed.length === 0) {
      setError("No valid rows found");
      return;
    }
    onImport(parsed);
    setText("");
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    onClose();
  }

  function handleClose() {
    setText("");
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    onClose();
  }

  return (
    <Modal open={open} onClose={handleClose} title="Import words">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          One word per line, comma-separated:{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
            spanish,english,tag1;tag2
          </code>
          . Blank lines and lines starting with{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
            #
          </code>{" "}
          are ignored.
        </p>

        <div>
          <span className="text-sm font-medium text-slate-700">Upload a file</span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            onChange={handleFile}
            className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-slate-700 file:hover:bg-slate-200"
          />
        </div>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">Or paste CSV</span>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setError(null);
            }}
            placeholder={"correr,to run,verb\nolor,smell,noun\ndulce,sweet,adjective"}
            rows={6}
            className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </label>

        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            {parsed.length} row{parsed.length === 1 ? "" : "s"} ready to import
          </span>
          {error && <span className="text-rose-600">{error}</span>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleImport}
            disabled={parsed.length === 0}
            className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Import {parsed.length || ""}
          </button>
        </div>
      </div>
    </Modal>
  );
}
