"use client";

import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSidebarState } from "@/lib/storage";

type Side = "left" | "right";

type Props = {
  side: Side;
  storageKey: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  collapsedWidth: number;
  collapseThreshold: number;
  hideBelow?: "lg" | "md";
  /** Optional header label shown above content when expanded. */
  headerLabel?: string;
  /** Children rendered inside the glass panel when expanded. */
  children: React.ReactNode;
  /** When collapsed, render a custom rail (e.g. icons). Falls back to a thin bar with expand button. */
  collapsedContent?: React.ReactNode;
  /** Hide chrome (header bar, collapse button) — sidebar content provides its own. */
  bare?: boolean;
};

export function ResizableSidebar({
  side,
  storageKey,
  defaultWidth,
  minWidth,
  maxWidth,
  collapsedWidth,
  collapseThreshold,
  hideBelow = "lg",
  headerLabel,
  children,
  collapsedContent,
  bare = false,
}: Props) {
  const { state, setWidth, toggleCollapsed, setCollapsed, hydrated } =
    useSidebarState(storageKey, {
      width: defaultWidth,
      collapsed: false,
    });

  const [dragging, setDragging] = useState(false);
  const liveWidthRef = useRef<number>(state.width);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    liveWidthRef.current = state.width;
  }, [state.width]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDragging(true);
      const startX = e.clientX;
      const startWidth = state.collapsed ? collapsedWidth : state.width;

      const onMove = (ev: MouseEvent) => {
        const delta = side === "left" ? ev.clientX - startX : startX - ev.clientX;
        const next = startWidth + delta;
        if (containerRef.current) {
          if (next < collapseThreshold) {
            containerRef.current.style.width = `${collapsedWidth}px`;
            liveWidthRef.current = collapsedWidth;
          } else {
            const clamped = Math.max(minWidth, Math.min(maxWidth, next));
            containerRef.current.style.width = `${clamped}px`;
            liveWidthRef.current = clamped;
          }
        }
      };

      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        setDragging(false);
        const final = liveWidthRef.current;
        if (final <= collapsedWidth) {
          setCollapsed(true);
        } else {
          setCollapsed(false);
          setWidth(final);
        }
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [
      side,
      state.width,
      state.collapsed,
      minWidth,
      maxWidth,
      collapsedWidth,
      collapseThreshold,
      setCollapsed,
      setWidth,
    ],
  );

  const onDoubleClick = useCallback(() => {
    setCollapsed(false);
    setWidth(defaultWidth);
  }, [defaultWidth, setCollapsed, setWidth]);

  const effectiveWidth = !hydrated
    ? defaultWidth
    : state.collapsed
      ? collapsedWidth
      : state.width;

  const hideClass =
    hideBelow === "lg" ? "hidden lg:flex" : hideBelow === "md" ? "hidden md:flex" : "flex";

  const handleEdge = side === "left" ? "right-0" : "left-0";
  const handleTranslate = side === "left" ? "translate-x-1/2" : "-translate-x-1/2";

  const CollapseIcon = state.collapsed
    ? side === "left"
      ? PanelLeftOpen
      : PanelRightOpen
    : side === "left"
      ? PanelLeftClose
      : PanelRightClose;

  return (
    <div
      ref={containerRef}
      className={`${hideClass} relative shrink-0 flex-col h-full`}
      style={{ width: `${effectiveWidth}px` }}
      data-collapsed={state.collapsed ? "true" : "false"}
      data-side={side}
    >
      {state.collapsed ? (
        <div className="glass-panel rounded-2xl h-full flex flex-col items-center py-3">
          <button
            type="button"
            onClick={toggleCollapsed}
            className="h-9 w-9 rounded-xl flex items-center justify-center text-slate-600 hover:bg-white/60 transition"
            aria-label={`Expand ${side} sidebar`}
            title={`Expand ${side} sidebar`}
          >
            <CollapseIcon className="h-4 w-4" />
          </button>
          {collapsedContent}
        </div>
      ) : bare ? (
        <div className="h-full overflow-hidden relative">
          <button
            type="button"
            onClick={toggleCollapsed}
            className={`absolute top-3 ${
              side === "left" ? "right-3" : "left-3"
            } z-10 h-7 w-7 rounded-lg flex items-center justify-center text-slate-500 hover:bg-white/60 hover:text-slate-700 transition`}
            aria-label={`Collapse ${side} sidebar`}
            title={`Collapse ${side} sidebar`}
          >
            <CollapseIcon className="h-4 w-4" />
          </button>
          {children}
        </div>
      ) : (
        <aside className="glass-panel rounded-2xl h-full flex flex-col overflow-hidden">
          {(headerLabel || true) && (
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/40 shrink-0">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {headerLabel ?? ""}
              </h2>
              <button
                type="button"
                onClick={toggleCollapsed}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-slate-500 hover:bg-white/60 hover:text-slate-700 transition"
                aria-label={`Collapse ${side} sidebar`}
                title={`Collapse ${side} sidebar`}
              >
                <CollapseIcon className="h-4 w-4" />
              </button>
            </div>
          )}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">{children}</div>
        </aside>
      )}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={`Resize ${side} sidebar`}
        onMouseDown={onMouseDown}
        onDoubleClick={onDoubleClick}
        className={`absolute top-0 bottom-0 ${handleEdge} ${handleTranslate} w-2 cursor-col-resize z-20 group`}
      >
        <div
          className={`mx-auto h-full w-px transition-colors ${
            dragging ? "bg-brand-400" : "bg-transparent group-hover:bg-brand-300/70"
          }`}
        />
      </div>
    </div>
  );
}
