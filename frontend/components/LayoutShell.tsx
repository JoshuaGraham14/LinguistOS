"use client";

import { usePathname } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { AppTopBar } from "./AppTopBar";
import { ResizableSidebar } from "./ResizableSidebar";
import { RightSidebar, rightSidebarHiddenForPath } from "./RightSidebar";
import { Sidebar } from "./Sidebar";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hideRight = rightSidebarHiddenForPath(pathname);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [leftToggle, setLeftToggle] = useState<() => void>(() => () => {});
  const [workspaceSwitchPulse, setWorkspaceSwitchPulse] = useState(false);
  const handleLeftToggle = useCallback(() => leftToggle(), [leftToggle]);
  const handleLeftToggleReady = useCallback((toggle: () => void) => {
    setLeftToggle(() => toggle);
  }, []);

  useEffect(() => {
    let timer: number | null = null;
    function handleWorkspaceChange() {
      setWorkspaceSwitchPulse(true);
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => setWorkspaceSwitchPulse(false), 420);
    }
    window.addEventListener("linguistos:workspace-change", handleWorkspaceChange);
    return () => {
      window.removeEventListener("linguistos:workspace-change", handleWorkspaceChange);
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  return (
    <div className="relative flex h-screen overflow-y-hidden overflow-x-visible">
      <ResizableSidebar
        side="left"
        storageKey="linguistos.leftSidebar"
        defaultWidth={256}
        minWidth={220}
        maxWidth={360}
        collapsedWidth={68}
        collapseThreshold={180}
        hideBelow="md"
        onStateChange={setLeftCollapsed}
        onToggleReady={handleLeftToggleReady}
      >
        <Sidebar />
      </ResizableSidebar>

      <div className="relative z-10 flex flex-1 flex-col min-w-0 overflow-hidden">
        <AppTopBar
          leftCollapsed={leftCollapsed}
          onToggleLeft={handleLeftToggle}
        />
        <main className="flex-1 min-w-0 overflow-y-auto px-5 lg:px-7 py-5 lg:py-6">
          {children}
        </main>
      </div>

      {!hideRight && (
        <ResizableSidebar
          side="right"
          storageKey="linguistos.rightSidebar"
          defaultWidth={340}
          minWidth={300}
          maxWidth={520}
          collapsedWidth={56}
          collapseThreshold={260}
        >
          <Suspense fallback={null}>
            <RightSidebar />
          </Suspense>
        </ResizableSidebar>
      )}

      {/* Full-viewport blur pulse on workspace switch only (event gated in storage). */}
      <div
        aria-hidden
        className={
          "pointer-events-none fixed inset-0 z-[200] transition-[opacity,backdrop-filter] duration-300 ease-out " +
          (workspaceSwitchPulse
            ? "opacity-100 backdrop-blur-[10px] bg-white/12"
            : "opacity-0 backdrop-blur-none bg-transparent")
        }
      />
    </div>
  );
}
