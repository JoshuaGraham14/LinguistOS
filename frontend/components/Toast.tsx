"use client";

interface ToastProps {
  message: string | null;
  /** Tailwind classes for positioning. Defaults to bottom-right. */
  className?: string;
}

export function Toast({
  message,
  className = "fixed bottom-24 right-6 z-50",
}: ToastProps) {
  if (!message) return null;
  return (
    <div
      className={`${className} rounded-xl bg-slate-900 text-white px-4 py-2 text-sm shadow-card`}
      role="status"
    >
      {message}
    </div>
  );
}
