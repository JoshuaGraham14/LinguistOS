import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type StatColor = "blue" | "green" | "orange" | "purple";

const COLOR_MAP: Record<StatColor, string> = {
  blue: "bg-gradient-to-br from-blue-400 to-blue-600",
  green: "bg-gradient-to-br from-emerald-400 to-emerald-600",
  orange: "bg-gradient-to-br from-orange-400 to-orange-600",
  purple: "bg-gradient-to-br from-fuchsia-500 to-purple-600",
};

export function StatCard({
  icon: Icon,
  value,
  label,
  color,
}: {
  icon: LucideIcon;
  value: string;
  label: string;
  color: StatColor;
}) {
  return (
    <div className="glass-card glass-gloss rounded-2xl p-6 flex flex-col gap-3">
      <div
        className={cn(
          "h-12 w-12 rounded-xl flex items-center justify-center shadow-glass",
          COLOR_MAP[color],
        )}
      >
        <Icon className="h-6 w-6 text-white" strokeWidth={2} />
      </div>
      <div className="relative">
        <div className="text-3xl font-bold text-slate-900">{value}</div>
        <div className="text-sm text-slate-500 mt-1">{label}</div>
      </div>
    </div>
  );
}
