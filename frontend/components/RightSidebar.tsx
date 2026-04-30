"use client";

import {
  BookOpen,
  Bot,
  ExternalLink,
  Layers,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Send,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useSidebar } from "@/components/ResizableSidebar";
import { cn } from "@/lib/cn";
import { formatWordDisplay, useProfile, useVocab } from "@/lib/storage";
import type { VocabItem } from "@/lib/types";

export function rightSidebarHiddenForPath(pathname: string): boolean {
  return false;
}

type Tab = "word" | "chat";

export function RightSidebar() {
  const { collapsed, toggle } = useSidebar();
  const [tab, setTab] = useState<Tab>("word");

  useEffect(() => {
    function onOpenWordPanel() {
      setTab("word");
      if (collapsed) toggle();
    }
    window.addEventListener("linguistos:open-word-panel", onOpenWordPanel);
    return () => window.removeEventListener("linguistos:open-word-panel", onOpenWordPanel);
  }, [collapsed, toggle]);

  if (collapsed) {
    return (
      <div className="glass-panel rounded-none h-full flex flex-col items-center py-3 gap-2">
        <button
          type="button"
          onClick={toggle}
          className="h-9 w-9 rounded-xl flex items-center justify-center text-slate-600 hover:bg-white/60 transition"
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <div className="h-px w-6 bg-white/40" />
        <button
          type="button"
          onClick={() => {
            setTab("word");
            toggle();
          }}
          className="h-9 w-9 rounded-xl flex items-center justify-center text-slate-600 hover:bg-white/60 transition"
          title="Word"
          aria-label="Open word panel"
        >
          <BookOpen className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => {
            setTab("chat");
            toggle();
          }}
          className="h-9 w-9 rounded-xl flex items-center justify-center text-slate-600 hover:bg-white/60 transition"
          title="AI Chat"
          aria-label="Open AI chat"
        >
          <Bot className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <aside className="glass-panel rounded-none h-full flex flex-col overflow-hidden">
      <div className="flex items-center gap-1 px-2 py-2 border-b border-white/40 shrink-0">
        <TabButton
          active={tab === "word"}
          onClick={() => setTab("word")}
          icon={<BookOpen className="h-3.5 w-3.5" />}
          label="Word"
        />
        <TabButton
          active={tab === "chat"}
          onClick={() => setTab("chat")}
          icon={<Bot className="h-3.5 w-3.5" />}
          label="AI Chat"
        />
        <div className="flex-1" />
        <button
          type="button"
          onClick={toggle}
          className="h-7 w-7 rounded-lg flex items-center justify-center text-slate-500 hover:bg-white/60 hover:text-slate-700 transition"
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden">
        {tab === "word" ? <WordTab /> : <ChatTab />}
      </div>
    </aside>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
        active
          ? "bg-white/80 text-slate-900 shadow-glass border border-white/60"
          : "text-slate-500 hover:bg-white/50 hover:text-slate-700",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function WordTab() {
  const searchParams = useSearchParams();
  const wordIdParam = searchParams.get("word_quick");
  const unknownSurface = (searchParams.get("word_surface") ?? "").trim();
  const wordId = Number(wordIdParam);
  const hasSelection = Number.isFinite(wordId) && wordId > 0;

  const { vocab, hydrated, addVocab } = useVocab();
  const { profile } = useProfile();
  const pathname = usePathname();
  const router = useRouter();
  const [addingUnknown, setAddingUnknown] = useState(false);

  const item = useMemo<VocabItem | undefined>(() => {
    if (!hasSelection) return undefined;
    return vocab.find((v) => v.id === wordId);
  }, [vocab, wordId, hasSelection]);

  if (!hasSelection) {
    if (unknownSurface) {
      return (
        <WordUnknownState
          surface={unknownSurface}
          adding={addingUnknown}
          onAdd={async () => {
            if (addingUnknown) return;
            setAddingUnknown(true);
            try {
              const added = await addVocab({ surfaceForm: unknownSurface });
              const next = new URLSearchParams(searchParams.toString());
              next.set("word_quick", String(added.id));
              next.delete("word_surface");
              const q = next.toString();
              router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
            } finally {
              setAddingUnknown(false);
            }
          }}
        />
      );
    }
    return <WordEmptyState />;
  }
  if (!hydrated) {
    return (
      <div className="p-4 text-xs text-slate-400">Loading word…</div>
    );
  }
  if (!item) {
    return (
      <div className="p-4 text-sm text-slate-500">
        That word isn&apos;t in this workspace.
      </div>
    );
  }
  return <WordDetails item={item} displayMode={profile.wordDisplayMode} />;
}

function WordUnknownState({
  surface,
  adding,
  onAdd,
}: {
  surface: string;
  adding: boolean;
  onAdd: () => Promise<void>;
}) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-6">
      <div className="h-12 w-12 rounded-2xl bg-amber-100/80 border border-amber-200/80 flex items-center justify-center text-amber-600 shadow-glass-inset mb-3">
        <BookOpen className="h-5 w-5" />
      </div>
      <h3 className="text-sm font-semibold text-slate-700">Not in vocab list</h3>
      <p className="mt-1 text-xs text-slate-500 max-w-[220px] leading-relaxed">
        &quot;{surface}&quot; is not in your workspace yet.
      </p>
      <button
        type="button"
        onClick={() => void onAdd()}
        disabled={adding}
        className="mt-3 rounded-xl bg-btn-purple text-white text-sm font-medium px-3 py-2 hover:brightness-110 disabled:opacity-60"
      >
        {adding ? "Adding..." : "Add to vocab list"}
      </button>
    </div>
  );
}

function WordEmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-6">
      <div className="h-12 w-12 rounded-2xl bg-white/60 border border-white/60 flex items-center justify-center text-slate-400 shadow-glass-inset mb-3">
        <BookOpen className="h-5 w-5" />
      </div>
      <h3 className="text-sm font-semibold text-slate-700">No word selected</h3>
      <p className="mt-1 text-xs text-slate-500 max-w-[220px] leading-relaxed">
        Click any word in a sentence, the lexicon, or your collection to see
        its definition here.
      </p>
    </div>
  );
}

function WordDetails({
  item,
  displayMode,
}: {
  item: VocabItem;
  displayMode: "lemma_first" | "as_encountered";
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const display = formatWordDisplay(item, displayMode);
  const mastery = item.mastery;
  const formsSeen = (item.surfaceForms ?? []).filter(
    (f) => f && f !== item.lemma,
  );

  function clearSelection() {
    const next = new URLSearchParams(searchParams.toString());
    next.delete("word_quick");
    const q = next.toString();
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">
              Definition
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mt-0.5 truncate">
              {display.primary}
            </h2>
            {display.secondary && (
              <p className="text-xs text-slate-500 truncate">
                {display.secondary}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={clearSelection}
            className="text-xs text-slate-500 hover:text-slate-700 transition"
            title="Clear selection"
          >
            Clear
          </button>
        </div>
        <p className="mt-2 text-sm text-slate-700">
          {item.glossPrimary || item.translation || (
            <span className="text-slate-400 italic">No translation yet</span>
          )}
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {item.pos && <Tag>{item.pos}</Tag>}
        {item.cefr && <Tag>{item.cefr}</Tag>}
        {item.gender && <Tag>{item.gender}</Tag>}
        {item.learned ? (
          <Tag tone="success">Learned</Tag>
        ) : (
          <Tag tone="muted">Learning</Tag>
        )}
      </div>

      {item.glosses && item.glosses.length > 1 && (
        <Section title="Meanings">
          <ul className="space-y-1">
            {item.glosses.slice(0, 6).map((g, i) => (
              <li key={i} className="text-sm text-slate-700">
                · {g}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {mastery && (
        <Section title="Mastery">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Box" value={`${mastery.box}`} />
            <Stat
              label="Strength"
              value={`${Math.round(mastery.strength * 100)}%`}
            />
            <Stat label="Streak" value={`${mastery.streak}`} />
            <Stat
              label="Next due"
              value={
                mastery.nextDue
                  ? new Date(mastery.nextDue).toLocaleDateString()
                  : "—"
              }
            />
          </div>
        </Section>
      )}

      {formsSeen.length > 0 && (
        <Section title="Forms seen">
          <div className="flex flex-wrap gap-1.5">
            {formsSeen.slice(0, 12).map((f) => (
              <span
                key={f}
                className="rounded-md bg-white/60 border border-white/60 px-2 py-0.5 text-xs text-slate-700"
              >
                {f}
              </span>
            ))}
          </div>
        </Section>
      )}

      <Section title="Practice">
        <div className="grid grid-cols-2 gap-2">
          <PracticeButton
            href={`/learn/flashcards?word=${item.id}`}
            icon={<Layers className="h-3.5 w-3.5" />}
            label="Flashcards"
          />
          <PracticeButton
            href={`/learn/sentences?word=${item.id}`}
            icon={<Pencil className="h-3.5 w-3.5" />}
            label="Sentences"
          />
        </div>
        <Link
          href={`/words/${item.id}`}
          className="mt-2 inline-flex items-center gap-1 text-xs text-brand-700 hover:text-brand-600 transition"
        >
          Open full word page
          <ExternalLink className="h-3 w-3" />
        </Link>
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="glass-card rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-2">
        {title}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/55 border border-white/50 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function Tag({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "success" | "muted";
}) {
  const toneClasses =
    tone === "success"
      ? "bg-emerald-100/80 text-emerald-700 border-emerald-200/80"
      : tone === "muted"
        ? "bg-slate-100/70 text-slate-500 border-slate-200/70"
        : "bg-brand-100/70 text-brand-700 border-brand-200/70";
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[11px] font-medium",
        toneClasses,
      )}
    >
      {children}
    </span>
  );
}

function PracticeButton({
  href,
  icon,
  label,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/70 border border-white/60 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-white shadow-glass transition"
    >
      {icon}
      {label}
    </Link>
  );
}

/* ---------- AI Chat (skeleton, non-functional) ---------- */

const SKELETON_MESSAGES: { role: "user" | "ai"; text: string }[] = [
  { role: "ai", text: "Hi! Ask me anything about your vocabulary or a sentence you're studying." },
  { role: "user", text: "What's the difference between ser and estar?" },
  {
    role: "ai",
    text: "Both translate to \"to be\" in English. Use ser for permanent traits, identity, and time. Use estar for states, locations, and ongoing conditions.",
  },
];

const SKELETON_SUGGESTIONS = [
  "Explain this word",
  "Use it in a sentence",
  "Conjugate this verb",
  "Why is it gendered?",
];

function ChatTab() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {SKELETON_MESSAGES.map((m, i) => (
          <div
            key={i}
            className={cn(
              "max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-snug",
              m.role === "user"
                ? "ml-auto bg-btn-purple text-white shadow-glass"
                : "mr-auto glass-card text-slate-700",
            )}
          >
            {m.text}
          </div>
        ))}
        <div className="mr-auto inline-flex items-center gap-1 text-xs text-slate-400 pl-2">
          <Sparkles className="h-3 w-3" />
          AI is offline — preview only
        </div>
      </div>

      <div className="p-3 border-t border-white/40 space-y-2 shrink-0">
        <div className="flex flex-wrap gap-1.5">
          {SKELETON_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              disabled
              className="rounded-full bg-white/55 border border-white/50 px-2.5 py-1 text-[11px] text-slate-600 opacity-70 cursor-not-allowed"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 rounded-xl bg-white/70 border border-white/60 shadow-glass-inset px-3 py-2">
          <input
            type="text"
            disabled
            placeholder="Ask AI…"
            className="flex-1 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none cursor-not-allowed"
          />
          <button
            type="button"
            disabled
            className="h-7 w-7 rounded-lg bg-btn-purple text-white flex items-center justify-center opacity-60 cursor-not-allowed shadow-glass"
            aria-label="Send (disabled)"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
