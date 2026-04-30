"use client";

import { Plus } from "lucide-react";
import { QuickCaptureForm } from "../QuickCaptureForm";

export function QuickCaptureWidget() {
  return (
    <div className="glass-card rounded-2xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-7 w-7 rounded-lg bg-btn-purple flex items-center justify-center text-white shadow-glass">
          <Plus className="h-4 w-4" strokeWidth={2.5} />
        </div>
        <h3 className="text-sm font-semibold text-slate-900">Quick add</h3>
      </div>
      <QuickCaptureForm variant="compact" />
    </div>
  );
}
