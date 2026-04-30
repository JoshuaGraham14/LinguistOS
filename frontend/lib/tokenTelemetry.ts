"use client";

declare global {
  interface Window {
    __linguistosTokenMetrics?: Record<string, number>;
  }
}

export function trackTokenMetric(event: string): void {
  if (typeof window === "undefined") return;
  const metrics = (window.__linguistosTokenMetrics ??= {});
  metrics[event] = (metrics[event] ?? 0) + 1;
}
