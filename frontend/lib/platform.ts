"use client";

/**
 * Best-effort Mac detection that avoids the deprecated
 * ``navigator.platform``. Falls back to Ctrl on the server and on
 * unidentified clients.
 */
export function isMacLike(): boolean {
  if (typeof navigator === "undefined") return false;
  type WithUAData = Navigator & { userAgentData?: { platform?: string } };
  const ua = navigator as WithUAData;
  const platformHint = ua.userAgentData?.platform ?? "";
  if (platformHint) return /mac/i.test(platformHint);
  return /mac|iphone|ipad|ipod/i.test(navigator.userAgent ?? "");
}

/** Cross-platform shortcut label, e.g. "⌘K" on macOS, "Ctrl+K" elsewhere. */
export function shortcutLabel(letter: string): string {
  return isMacLike() ? `⌘${letter.toUpperCase()}` : `Ctrl+${letter.toUpperCase()}`;
}
