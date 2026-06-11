"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import type { SavedViewLayout } from "@/lib/types";

const LAYOUT_OPTIONS: { value: SavedViewLayout; label: string }[] = [
  { value: "table", label: "Table" },
  { value: "gallery", label: "Cards" },
  { value: "board", label: "Board" },
];

const ICON_PRESETS = ["📋", "🖼️", "📅", "📚", "✨", "🎯"];

export function CreateViewModal({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: {
    name: string;
    layout: SavedViewLayout;
    icon: string | null;
  }) => void;
}) {
  const [name, setName] = useState("New view");
  const [layout, setLayout] = useState<SavedViewLayout>("table");
  const [icon, setIcon] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName("New view");
    setLayout("table");
    setIcon(null);
  }, [open]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onSubmit({ name: trimmed, layout, icon });
    onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title="Create view">
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </label>
        <div>
          <span className="text-sm font-medium text-slate-700">Layout</span>
          <div className="mt-2 flex flex-col gap-1">
            {LAYOUT_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-50 cursor-pointer text-sm"
              >
                <input
                  type="radio"
                  name="layout"
                  checked={layout === opt.value}
                  onChange={() => setLayout(opt.value)}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>
        <div>
          <span className="text-sm font-medium text-slate-700">Icon (optional)</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {ICON_PRESETS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                onClick={() => setIcon(icon === emoji ? null : emoji)}
                className={`h-9 w-9 rounded-lg border text-lg ${
                  icon === emoji
                    ? "border-brand-300 bg-brand-50"
                    : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim()}
            className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 transition"
          >
            Create view
          </button>
        </div>
      </form>
    </Modal>
  );
}
