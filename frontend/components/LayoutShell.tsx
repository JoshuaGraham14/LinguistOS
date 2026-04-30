"use client";

import { usePathname } from "next/navigation";
import { ResizableSidebar } from "./ResizableSidebar";
import { RightSidebarContent, rightSidebarHiddenForPath } from "./RightSidebar";
import { Sidebar } from "./Sidebar";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hideRight = rightSidebarHiddenForPath(pathname);

  return (
    <div className="flex h-screen p-4 lg:p-5 gap-4 overflow-hidden">
      <ResizableSidebar
        side="left"
        storageKey="linguistos.leftSidebar"
        defaultWidth={256}
        minWidth={220}
        maxWidth={360}
        collapsedWidth={64}
        collapseThreshold={180}
        hideBelow="md"
        bare
      >
        <Sidebar />
      </ResizableSidebar>

      <main className="flex-1 min-w-0 overflow-y-auto">{children}</main>

      {!hideRight && (
        <ResizableSidebar
          side="right"
          storageKey="linguistos.rightSidebar"
          defaultWidth={320}
          minWidth={280}
          maxWidth={480}
          collapsedWidth={56}
          collapseThreshold={240}
          headerLabel="Context"
        >
          <RightSidebarContent />
        </ResizableSidebar>
      )}
    </div>
  );
}
