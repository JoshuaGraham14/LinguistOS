"use client";

import { Download, Upload } from "lucide-react";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ImportWordsModal } from "@/components/vocab/ImportWordsModal";
import { VocabBoardView } from "@/components/vocab/VocabBoardView";
import { VocabGalleryView } from "@/components/vocab/VocabGalleryView";
import { VocabTableView, toggleSortRule } from "@/components/vocab/VocabTableView";
import { VocabToolbar } from "@/components/vocab/VocabToolbar";
import {
  ViewSettingsPanel,
  type ViewSettingsSection,
} from "@/components/vocab/ViewSettingsPanel";
import { ViewTabBar } from "@/components/vocab/ViewTabBar";
import { WordFormModal } from "@/components/vocab/WordFormModal";
import { isEmptyLexiconQuery, serializeLexiconQuery } from "@/lib/lexicon-query";
import {
  useProfile,
  useSavedViews,
  useVocab,
  useWorkspaces,
} from "@/lib/storage";
import type { SavedViewLayout, VocabItem } from "@/lib/types";
import { useDebouncedViewPatch } from "@/lib/useDebouncedViewPatch";
import { buildVocabCsv, downloadVocabCsv } from "@/lib/vocab-csv";
import { applyViewPipeline } from "@/lib/vocab-view";

function VocabPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { activeWorkspace } = useWorkspaces();
  const { views, hydrated: viewsHydrated, createView, patchView } = useSavedViews();
  const {
    vocab,
    hydrated: vocabHydrated,
    addVocab,
    removeVocab,
    updateVocab,
    toggleLearned,
  } = useVocab();
  const { profile } = useProfile();

  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<VocabItem | null>(null);

  const viewIdParam = searchParams.get("view");
  const editParam = searchParams.get("edit");
  const parsedViewId = viewIdParam ? Number(viewIdParam) : null;

  const activeView = useMemo(() => {
    if (views.length === 0) return null;
    if (parsedViewId && views.some((v) => v.id === parsedViewId)) {
      return views.find((v) => v.id === parsedViewId) ?? views[0]!;
    }
    return views[0]!;
  }, [views, parsedViewId]);

  const { config, setConfig, saveStatus } = useDebouncedViewPatch(
    activeView,
    patchView,
  );

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSection, setSettingsSection] =
    useState<ViewSettingsSection | null>(null);

  useEffect(() => {
    if (!vocabHydrated || !editParam) return;
    const id = Number(editParam);
    if (!Number.isFinite(id)) return;
    const target = vocab.find((v) => v.id === id);
    if (target) setEditing(target);
  }, [editParam, vocabHydrated, vocab]);

  function closeEditing() {
    setEditing(null);
    if (editParam) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("edit");
      const qs = params.toString();
      router.replace(qs ? `/vocab?${qs}` : "/vocab", { scroll: false });
    }
  }

  const layoutParam = searchParams.get("layout");

  const selectView = useCallback(
    (viewId: number) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("view", String(viewId));
      params.delete("layout");
      router.replace(`/vocab?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  useEffect(() => {
    if (!viewsHydrated || views.length === 0 || layoutParam == null) return;
    const match = views.find((v) => v.layout === layoutParam);
    if (match && match.id !== activeView?.id) {
      selectView(match.id);
    }
  }, [viewsHydrated, views, layoutParam, activeView?.id, selectView]);

  useEffect(() => {
    if (!viewsHydrated || !activeView) return;
    const current = searchParams.get("view");
    const target = String(activeView.id);
    if (current !== target) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("view", target);
      params.delete("layout");
      router.replace(`/vocab?${params.toString()}`, { scroll: false });
    }
  }, [activeView, viewsHydrated, router, searchParams]);

  const pipeline = useMemo(() => {
    if (!config) return { items: [], groups: null };
    return applyViewPipeline(vocab, config);
  }, [vocab, config]);

  const loading = !viewsHydrated || !vocabHydrated || !config;

  const handleCreateView = useCallback(async () => {
    const name = window.prompt("View name", "New view");
    if (!name?.trim()) return;
    const created = await createView({ name: name.trim(), layout: "table" });
    selectView(created.id);
  }, [createView, selectView]);

  const handleLayoutChange = useCallback(
    async (layout: SavedViewLayout) => {
      if (!activeView) return;
      await patchView(activeView.id, { layout });
    },
    [activeView, patchView],
  );

  const flashcardsHref = useMemo(() => {
    if (activeView) {
      return `/learn/flashcards?view=${activeView.id}`;
    }
    if (config && !isEmptyLexiconQuery(config.query)) {
      const encoded = serializeLexiconQuery(config.query);
      return `/learn/flashcards?filter=${encodeURIComponent(encoded)}`;
    }
    return "/learn/flashcards";
  }, [activeView, config]);

  const openSettings = (section: ViewSettingsSection | null) => {
    setSettingsSection(section);
    setSettingsOpen(true);
  };

  if (!viewsHydrated) {
    return <div className="text-slate-400 text-center py-12">Loading…</div>;
  }

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Vocabulary</h1>
          <p className="text-slate-500 mt-1">
            {activeWorkspace && (
              <span>
                {activeWorkspace.emojiOrFlag} {activeWorkspace.name}
                {" · "}
              </span>
            )}
            {vocabHydrated
              ? `${pipeline.items.length} of ${vocab.length} words`
              : "Loading…"}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setImportOpen(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-medium px-4 py-2.5 hover:bg-slate-50 transition"
          >
            <Upload className="h-4 w-4" strokeWidth={2.5} />
            Import
          </button>
          <button
            type="button"
            onClick={() =>
              downloadVocabCsv(
                "vocabulary.csv",
                buildVocabCsv(vocab),
              )
            }
            className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-medium px-4 py-2.5 hover:bg-slate-50 transition"
          >
            <Download className="h-4 w-4" strokeWidth={2.5} />
            Export
          </button>
        </div>
      </header>

      <ViewTabBar
        views={views}
        activeViewId={activeView?.id ?? null}
        onSelect={selectView}
        onCreate={() => void handleCreateView()}
      />

      <VocabToolbar
        search={config?.query.search ?? ""}
        onSearchChange={(search) =>
          setConfig((prev) => ({ ...prev, query: { ...prev.query, search } }))
        }
        saveStatus={saveStatus}
        hasActiveFilters={config ? !isEmptyLexiconQuery(config.query) : false}
        hasActiveSort={(config?.sorts.length ?? 0) > 0}
        settingsOpen={settingsOpen}
        onToggleSettings={() => {
          setSettingsSection(null);
          setSettingsOpen((o) => !o);
        }}
        onOpenFilter={() => openSettings("filter")}
        onOpenSort={() => openSettings("sort")}
        flashcardsHref={flashcardsHref}
        onNew={() => setAddOpen(true)}
      />

      <div className="flex gap-4 items-start">
        <div className="flex-1 min-w-0 space-y-4">
          {activeView?.layout === "table" && config && (
            <VocabTableView
              items={pipeline.items}
              config={config}
              loading={loading}
              wordDisplayMode={profile.wordDisplayMode}
              onSort={(field) =>
                setConfig((prev) => ({
                  ...prev,
                  sorts: toggleSortRule(prev.sorts, field),
                }))
              }
            />
          )}
          {activeView?.layout === "gallery" && config && (
            <VocabGalleryView
              items={pipeline.items}
              config={config}
              loading={loading}
              onEdit={setEditing}
              onDelete={(id) => void removeVocab(id)}
              onToggleLearned={(id) => void toggleLearned(id)}
            />
          )}
          {activeView?.layout === "board" && config && (
            <VocabBoardView
              items={pipeline.items}
              config={config}
              loading={loading}
              onUpdateField={(id, field, value) => {
                if (field === "learned") {
                  void updateVocab(id, { learned: Boolean(value) });
                } else if (field === "cefr") {
                  void updateVocab(id, { cefr: String(value) || null });
                }
              }}
            />
          )}
        </div>

        {settingsOpen && config && activeView && (
          <ViewSettingsPanel
            open={settingsOpen}
            section={settingsSection}
            layout={activeView.layout}
            config={config}
            onLayoutChange={(layout) => void handleLayoutChange(layout)}
            onConfigChange={setConfig}
            onClose={() => setSettingsOpen(false)}
          />
        )}
      </div>

      <WordFormModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add word"
        submitLabel="Add word"
        sourceLanguageLabel={activeWorkspace?.language.toUpperCase() ?? "Source"}
        workspaceId={activeWorkspace?.id ?? null}
        onSubmit={(values) => {
          void addVocab(values);
        }}
      />
      <WordFormModal
        open={Boolean(editing)}
        onClose={closeEditing}
        title="Edit word"
        submitLabel="Save changes"
        sourceLanguageLabel={activeWorkspace?.language.toUpperCase() ?? "Source"}
        workspaceId={activeWorkspace?.id ?? null}
        initial={editing}
        onSubmit={(values) => {
          if (editing) void updateVocab(editing.id, values);
        }}
      />
      <ImportWordsModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={(rows) => {
          rows.forEach((r) => {
            void addVocab(r);
          });
        }}
      />
    </div>
  );
}

export default function VocabPage() {
  return (
    <Suspense
      fallback={<div className="text-slate-400 text-center py-12">Loading…</div>}
    >
      <VocabPageInner />
    </Suspense>
  );
}
