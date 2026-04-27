import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";

type QuickActionColor = "blue" | "green" | "red" | "purple";

const COLOR_MAP: Record<QuickActionColor, string> = {
  blue: "bg-gradient-to-br from-blue-400 to-blue-600",
  green: "bg-gradient-to-br from-emerald-400 to-emerald-600",
  red: "bg-gradient-to-br from-rose-400 to-rose-600",
  purple: "bg-gradient-to-br from-fuchsia-500 to-purple-600",
};

export function QuickActionCard({
  href,
  label,
  icon: Icon,
  color,
}: {
  href: string;
  label: string;
  icon: LucideIcon;
  color: QuickActionColor;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-2xl shadow-card p-6 flex flex-col items-center justify-center gap-3 text-white transition hover:brightness-110 hover:-translate-y-0.5 aspect-square",
        COLOR_MAP[color],
      )}
    >
      <Icon className="h-8 w-8" strokeWidth={2} />
      <div className="font-semibold">{label}</div>
    </Link>
  );
}
