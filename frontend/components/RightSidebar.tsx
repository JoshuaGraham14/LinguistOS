"use client";

import { usePathname } from "next/navigation";
import { KeyboardShortcutsWidget } from "./right-sidebar/KeyboardShortcutsWidget";
import { QuickCaptureWidget } from "./right-sidebar/QuickCaptureWidget";
import { RecentlyCapturedWidget } from "./right-sidebar/RecentlyCapturedWidget";
import { TodayProgressWidget } from "./right-sidebar/TodayProgressWidget";

export function rightSidebarHiddenForPath(pathname: string): boolean {
  return pathname === "/settings";
}

function widgetsForPath(pathname: string): React.ReactNode {
  if (pathname.startsWith("/learn/flashcards")) {
    return (
      <>
        <KeyboardShortcutsWidget />
        <RecentlyCapturedWidget limit={5} />
      </>
    );
  }
  if (pathname.startsWith("/learn/sentences")) {
    return (
      <>
        <RecentlyCapturedWidget limit={6} />
        <QuickCaptureWidget />
      </>
    );
  }
  if (pathname.startsWith("/learn")) {
    return (
      <>
        <TodayProgressWidget />
        <RecentlyCapturedWidget limit={5} />
      </>
    );
  }
  if (pathname.startsWith("/words/") && pathname !== "/words") {
    return (
      <>
        <TodayProgressWidget />
        <QuickCaptureWidget />
      </>
    );
  }
  if (pathname.startsWith("/words")) {
    return (
      <>
        <RecentlyCapturedWidget limit={6} />
        <QuickCaptureWidget />
      </>
    );
  }
  if (pathname.startsWith("/lexicon")) {
    return (
      <>
        <TodayProgressWidget />
        <RecentlyCapturedWidget limit={5} />
      </>
    );
  }
  return (
    <>
      <TodayProgressWidget />
      <RecentlyCapturedWidget limit={5} />
      <QuickCaptureWidget />
    </>
  );
}

export function RightSidebarContent() {
  const pathname = usePathname();
  return <>{widgetsForPath(pathname)}</>;
}
