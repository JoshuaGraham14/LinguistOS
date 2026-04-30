"use client";

import { usePathname } from "next/navigation";
import { ResizableSidebar } from "./ResizableSidebar";
import { RightSidebar, rightSidebarHiddenForPath } from "./RightSidebar";
import { Sidebar } from "./Sidebar";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hideRight = rightSidebarHiddenForPath(pathname);

  return (
    <div className="flex h-screen overflow-hidden">
      <ResizableSidebar
        side="left"
        storageKey="linguistos.leftSidebar"
        defaultWidth={256}
        minWidth={220}
        maxWidth={360}
        collapsedWidth={68}
        collapseThreshold={180}
        hideBelow="md"
      >
        <Sidebar />
      </ResizableSidebar>

      <main className="flex-1 min-w-0 overflow-y-auto px-5 lg:px-7 py-5 lg:py-6">
        {children}
      </main>

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
          <RightSidebar />
        </ResizableSidebar>
      )}
    </div>
  );
}
