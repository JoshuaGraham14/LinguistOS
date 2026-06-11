"use client";

import { Download, GraduationCap, Upload } from "lucide-react";
import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CreateViewModal } from "@/components/vocab/CreateViewModal";
import { ImportWordsModal } from "@/components/vocab/ImportWordsModal";
import { RenameViewModal } from "@/components/vocab/RenameViewModal";
import { VocabBoardView } from "@/components/vocab/VocabBoardView";
import { VocabGalleryView } from "@/components/vocab/VocabGalleryView";
import { VocabTableView, toggleSortRule } from "@/components/vocab/VocabTableView";
import {
  VocabDatabaseToolbar,
  type VocabPopoverId,
} from "@/components/vocab/VocabDatabaseToolbar";
import { ViewTabBar } from "@/components/vocab/ViewTabBar";
import { WordFormModal } from "@/components/vocab/WordFormModal";
import { Modal } from "@/components/Modal";
import {
  isEmptyLexiconQuery,
  parseLexiconQuery,
  serializeLexiconQuery,
} from "@/lib/lexicon-query";
import {
  useProfile,
  useSavedViews,
  useVocab,
  useWorkspaces,
} from "@/lib/storage";
import type { SavedView, SavedViewLayout, VocabItem } from "@/lib/types";
import { useDebouncedViewPatch } from "@/lib/useDebouncedViewPatch";
import { buildVocabCsv, downloadVocabCsv } from "@/lib/vocab-csv";
import { applyViewPipeline, defaultViewConfig } from "@/lib/vocab-view";

function VocabPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { activeWorkspace } = useWorkspaces();
  const {
    views,
    hydrated: viewsHydrated,
    createView,
    patchView,
    removeView,
  } = useSavedViews();
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
  const [createViewOpen, setCreateViewOpen] = useState(false);
  const [renameView, setRenameView] = useState<SavedView | null>(null);
  const [deleteView, setDeleteView] = useState<SavedView | null>(null);

  const viewIdParam = searchParams.get("view");
  const editParam = searchParams.get("edit");
  const filterParam = searchParams.get("filter");
  const parsedViewId = viewIdParam ? Number(viewIdParam) : null;
  const appliedFilterRef = useRef<string | null>(null);

  const activeView = useMemo(() => {
    if (views.length === 0) return null;
    if (parsedViewId && views.some((v) => v.id === parsedViewId)) {
      return views.find((v) => v.id === parsedViewId) ?? views[0]!;
    }
    return views[0]!;
  }, [views, parsedViewId]);

  const { config, setConfig, flush, saveStatus } = useDebouncedViewPatch(
    activeView,
    patchView,
  );

  const [activePopover, setActivePopover] = useState<VocabPopoverId>(null);

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

  useEffect(() => {
    if (!filterParam || !config || appliedFilterRef.current === filterParam) {
      return;
    }
    const query = parseLexiconQuery(decodeURIComponent(filterParam));
    if (isEmptyLexiconQuery(query)) return;
    appliedFilterRef.current = filterParam;
    setConfig((prev) => ({ ...prev, query }));
    const params = new URLSearchParams(searchParams.toString());
    params.delete("filter");
    const qs = params.toString();
    router.replace(qs ? `/vocab?${qs}` : "/vocab", { scroll: false });
  }, [filterParam, config, setConfig, router, searchParams]);

  const pipeline = useMemo(() => {
    if (!config) return { items: [], groups: null };
    return applyViewPipeline(vocab, config);
  }, [vocab, config]);

  const loading = !viewsHydrated || !vocabHydrated || !config;

  const handleCreateView = useCallback(
    async (input: {
      name: string;
      layout: SavedViewLayout;
      icon: string | null;
    }) => {
      const created = await createView({
        name: input.name,
        layout: input.layout,
        icon: input.icon,
        config: defaultViewConfig(input.layout),
      });
      selectView(created.id);
    },
    [createView, selectView],
  );

  const handleDuplicateView = useCallback(
    async (view: SavedView) => {
      const created = await createView({
        name: `${view.name} copy`,
        layout: view.layout,
        icon: view.icon,
        config: view.config,
      });
      selectView(created.id);
    },
    [createView, selectView],
  );

  const handleRenameView = useCallback(
    async (name: string) => {
      if (!renameView) return;
      await patchView(renameView.id, { name });
    },
    [renameView, patchView],
  );

  const handleDeleteView = useCallback(async () => {
    if (!deleteView || views.length <= 1) return;
    const deletingId = deleteView.id;
    const fallback = views.find((v) => v.id !== deletingId);
    await removeView(deletingId);
    if (activeView?.id === deletingId && fallback) {
      selectView(fallback.id);
    }
    setDeleteView(null);
  }, [deleteView, views, removeView, activeView?.id, selectView]);

  const handleLayoutChange = useCallback(
    async (layout: SavedViewLayout) => {
      if (!activeView) return;
      await flush();
      await patchView(activeView.id, { layout });
    },
    [activeView, patchView, flush],
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

  function togglePopover(id: Exclude<VocabPopoverId, null>) {
    setActivePopover((prev) => (prev === id ? null : id));
  }

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
          <Link
            href={flashcardsHref}
            className="inline-flex items-center gap-2 rounded-xl bg-fuchsia-600 text-white font-medium px-4 py-2.5 shadow-soft hover:bg-fuchsia-700 transition"
          >
            <GraduationCap className="h-4 w-4" strokeWidth={2.5} />
            Practice this view
          </Link>
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
                buildVocabCsv(pipeline.items),
              )
            }
            className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-medium px-4 py-2.5 hover:bg-slate-50 transition"
          >
            <Download className="h-4 w-4" strokeWidth={2.5} />
            Export
          </button>
        </div>
      </header>

      <div className="flex items-center border-b border-slate-200/80">
        <div className="flex-1 min-w-0 overflow-x-auto">
          <ViewTabBar
            views={views}
            activeViewId={activeView?.id ?? null}
            onSelect={selectView}
            onCreate={() => setCreateViewOpen(true)}
            onRename={setRenameView}
            onDuplicate={(view) => void handleDuplicateView(view)}
            onDelete={setDeleteView}
          />
        </div>
        {config && activeView && (
          <VocabDatabaseToolbar
            search={config.query.search}
            onSearchChange={(search) =>
              setConfig((prev) => ({ ...prev, query: { ...prev.query, search } }))
            }
            saveStatus={saveStatus}
            activePopover={activePopover}
            onTogglePopover={togglePopover}
            hasActiveFilters={!isEmptyLexiconQuery(config.query)}
            hasActiveSort={config.sorts.length > 0}
            hasGroup={Boolean(config.groupBy)}
            config={config}
            layout={activeView.layout}
            onLayoutChange={(layout) => void handleLayoutChange(layout)}
            onConfigChange={setConfig}
            onNew={() => setAddOpen(true)}
          />
        )}
      </div>

      <div className="relative">
        <div className="min-w-0 space-y-4">
          {activeView?.layout === "table" && config && (
            <VocabTableView
              items={pipeline.items}
              groups={pipeline.groups}
              config={config}
              loading={loading}
              wordDisplayMode={profile.wordDisplayMode}
              onSort={(field) =>
                setConfig((prev) => ({
                  ...prev,
                  sorts: toggleSortRule(prev.sorts, field),
                }))
              }
              onConfigChange={setConfig}
              onColumnMenuOpen={() => setActivePopover(null)}
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
      <CreateViewModal
        open={createViewOpen}
        onClose={() => setCreateViewOpen(false)}
        onSubmit={(input) => void handleCreateView(input)}
      />
      <RenameViewModal
        open={Boolean(renameView)}
        initialName={renameView?.name ?? ""}
        onClose={() => setRenameView(null)}
        onSubmit={(name) => void handleRenameView(name)}
      />
      <Modal
        open={Boolean(deleteView)}
        onClose={() => setDeleteView(null)}
        title="Delete view"
      >
        <p className="text-slate-600 text-sm">
          Delete &ldquo;{deleteView?.name}&rdquo;? This cannot be undone.
        </p>
        <div className="flex justify-end gap-2 mt-6">
          <button
            type="button"
            onClick={() => setDeleteView(null)}
            className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleDeleteView()}
            className="px-5 py-2 rounded-xl bg-rose-600 text-white font-medium hover:bg-rose-700 transition"
          >
            Delete
          </button>
        </div>
      </Modal>
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
