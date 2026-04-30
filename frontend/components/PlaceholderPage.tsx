import type { LucideIcon } from "lucide-react";

export function PlaceholderPage({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="glass-card glass-gloss rounded-2xl p-12 flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center shadow-glass mb-5 relative">
        <Icon className="h-8 w-8 text-white" strokeWidth={2} />
      </div>
      <h1 className="text-3xl font-bold text-slate-900">{title}</h1>
      <p className="text-slate-500 mt-2 max-w-md">{description}</p>
      <div className="mt-6 px-4 py-1.5 rounded-full bg-slate-100 text-slate-500 text-xs font-medium">
        Coming soon
      </div>
    </div>
  );
}
