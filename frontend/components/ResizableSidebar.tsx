"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useSidebarState } from "@/lib/storage";

type Side = "left" | "right";

type SidebarCtx = {
  collapsed: boolean;
  toggle: () => void;
  side: Side;
};

const SidebarContext = createContext<SidebarCtx | null>(null);

export function useSidebar(): SidebarCtx {
  const ctx = useContext(SidebarContext);
  if (!ctx) {
    throw new Error("useSidebar must be used inside ResizableSidebar");
  }
  return ctx;
}

type Props = {
  side: Side;
  storageKey: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  collapsedWidth: number;
  collapseThreshold: number;
  hideBelow?: "lg" | "md";
  onStateChange?: (collapsed: boolean) => void;
  onToggleReady?: (toggle: () => void) => void;
  children: React.ReactNode;
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
  onStateChange,
  onToggleReady,
  children,
}: Props) {
  const { state, setWidth, toggleCollapsed, setCollapsed, hydrated } =
    useSidebarState(storageKey, {
      width: defaultWidth,
      collapsed: false,
    });

  const [dragging, setDragging] = useState(false);
  // Tracks whether the drag has crossed the collapse threshold so children can
  // swap to/from icon-only layout in real time. Synced via a ref to keep
  // mousemove cheap (only triggers a re-render when the boolean flips).
  const [liveCollapsed, setLiveCollapsed] = useState(state.collapsed);
  const liveCollapsedRef = useRef(state.collapsed);
  const liveWidthRef = useRef<number>(state.width);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    liveWidthRef.current = state.width;
  }, [state.width]);

  // Sync liveCollapsed with state.collapsed for the "toggle via button" path.
  // Asymmetric: collapsing swaps to icon layout immediately (looks like the
  // panel squeezes around them); expanding keeps the icon layout until the
  // width transition finishes, so labels never render inside a too-narrow
  // panel.
  useEffect(() => {
    if (dragging) return;
    if (state.collapsed) {
      liveCollapsedRef.current = true;
      setLiveCollapsed(true);
      return;
    }
    const t = window.setTimeout(() => {
      liveCollapsedRef.current = false;
      setLiveCollapsed(false);
    }, 220);
    return () => window.clearTimeout(t);
  }, [state.collapsed, dragging]);

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
            if (!liveCollapsedRef.current) {
              liveCollapsedRef.current = true;
              setLiveCollapsed(true);
            }
          } else {
            const clamped = Math.max(minWidth, Math.min(maxWidth, next));
            containerRef.current.style.width = `${clamped}px`;
            liveWidthRef.current = clamped;
            if (liveCollapsedRef.current) {
              liveCollapsedRef.current = false;
              setLiveCollapsed(false);
            }
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

  // Effective collapsed for children: live during drag, persisted after.
  const childCollapsed = dragging ? liveCollapsed : state.collapsed;

  useEffect(() => {
    onStateChange?.(childCollapsed);
  }, [childCollapsed, onStateChange]);

  useEffect(() => {
    if (!onToggleReady) return;
    onToggleReady(() => toggleCollapsed());
  }, [onToggleReady, toggleCollapsed]);

  const stackClass =
    side === "left" ? "z-30" : side === "right" ? "z-20" : "z-10";

  return (
    <SidebarContext.Provider
      value={{ collapsed: childCollapsed, toggle: toggleCollapsed, side }}
    >
      <div
        ref={containerRef}
        className={`${hideClass} ${stackClass} relative shrink-0 flex-col h-full overflow-visible`}
        style={{
          width: `${effectiveWidth}px`,
          transition: dragging
            ? "none"
            : "width 220ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
        data-collapsed={state.collapsed ? "true" : "false"}
        data-live-collapsed={childCollapsed ? "true" : "false"}
        data-side={side}
      >
        <div className="h-full">{children}</div>
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
    </SidebarContext.Provider>
  );
}
