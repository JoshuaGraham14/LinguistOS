"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type AppHistoryContextValue = {
  canBack: boolean;
  canForward: boolean;
  goBack: () => void;
  goForward: () => void;
};

const AppHistoryContext = createContext<AppHistoryContextValue | null>(null);

function currentUrlFromWindow(pathname: string): string {
  if (typeof window === "undefined") return pathname;
  return `${pathname}${window.location.search ?? ""}`;
}

export function AppHistoryProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const stackRef = useRef<string[]>([]);
  const indexRef = useRef(-1);
  const navigatingRef = useRef<"back" | "forward" | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const current = currentUrlFromWindow(pathname);

    if (stackRef.current.length === 0) {
      stackRef.current = [current];
      indexRef.current = 0;
      setVersion((v) => v + 1);
      return;
    }

    if (navigatingRef.current === "back") {
      indexRef.current = Math.max(0, indexRef.current - 1);
      navigatingRef.current = null;
      setVersion((v) => v + 1);
      return;
    }

    if (navigatingRef.current === "forward") {
      indexRef.current = Math.min(stackRef.current.length - 1, indexRef.current + 1);
      navigatingRef.current = null;
      setVersion((v) => v + 1);
      return;
    }

    const nextStack = stackRef.current.slice(0, indexRef.current + 1);
    if (nextStack[nextStack.length - 1] !== current) {
      nextStack.push(current);
      stackRef.current = nextStack;
      indexRef.current = nextStack.length - 1;
      setVersion((v) => v + 1);
    }
  }, [pathname]);

  useEffect(() => {
    function handleWorkspaceChange() {
      // Workspace switches are context resets: start fresh at dashboard.
      stackRef.current = ["/"];
      indexRef.current = 0;
      navigatingRef.current = null;
      setVersion((v) => v + 1);
      if (pathname !== "/") {
        router.push("/");
      }
    }
    window.addEventListener("linguistos:workspace-change", handleWorkspaceChange);
    return () =>
      window.removeEventListener("linguistos:workspace-change", handleWorkspaceChange);
  }, [pathname, router]);

  const canBack = indexRef.current > 0;
  const canForward = indexRef.current >= 0 && indexRef.current < stackRef.current.length - 1;

  const goBack = useCallback(() => {
    if (!canBack) return;
    navigatingRef.current = "back";
    router.back();
  }, [canBack, router]);

  const goForward = useCallback(() => {
    if (!canForward) return;
    navigatingRef.current = "forward";
    router.forward();
  }, [canForward, router]);

  const value = useMemo(
    () => ({ canBack, canForward, goBack, goForward }),
    [canBack, canForward, goBack, goForward, version],
  );

  return <AppHistoryContext.Provider value={value}>{children}</AppHistoryContext.Provider>;
}

export function useAppHistory() {
  const ctx = useContext(AppHistoryContext);
  if (!ctx) {
    throw new Error("useAppHistory must be used within AppHistoryProvider");
  }
  return ctx;
}
