"use client";

import {
  getVocabProperty,
  hiddenVocabProperties,
} from "@/lib/vocab-properties";
import type { SortDirection } from "@/lib/types";
import {
  canHideProperty,
  effectiveSorts,
  hideProperty,
  removeSortRule,
  setPrimarySortRule,
  showProperty,
  type VocabViewConfig,
} from "@/lib/vocab-view";
import {
  ContextMenu,
  ContextMenuItem,
  ContextMenuSeparator,
} from "./ContextMenu";

export function ColumnHeaderMenu({
  propertyKey,
  config,
  x,
  y,
  open,
  onClose,
  onConfigChange,
}: {
  propertyKey: string | null;
  config: VocabViewConfig;
  x: number;
  y: number;
  open: boolean;
  onClose: () => void;
  onConfigChange: (updater: (prev: VocabViewConfig) => VocabViewConfig) => void;
}) {
  const prop = propertyKey ? getVocabProperty(propertyKey) : null;
  const activeSorts = effectiveSorts(config.sorts);
  const activeSort = propertyKey
    ? activeSorts.find((s) => s.field === propertyKey)
    : null;
  const hidden = hiddenVocabProperties(config.visibleProperties);

  function applySort(direction: SortDirection) {
    if (!propertyKey) return;
    onConfigChange((prev) => ({
      ...prev,
      sorts: setPrimarySortRule(prev.sorts, propertyKey, direction),
    }));
    onClose();
  }

  if (!prop || !propertyKey) return null;

  return (
    <ContextMenu open={open} x={x} y={y} onClose={onClose} minWidth={200}>
      {prop.sortable && (
        <>
          <ContextMenuItem onClick={() => applySort("asc")}>
            Sort ascending
            {activeSort?.direction === "asc" ? " ✓" : ""}
          </ContextMenuItem>
          <ContextMenuItem onClick={() => applySort("desc")}>
            Sort descending
            {activeSort?.direction === "desc" ? " ✓" : ""}
          </ContextMenuItem>
          {config.sorts.some((s) => s.field === propertyKey) && (
            <ContextMenuItem
              onClick={() => {
                onConfigChange((prev) => ({
                  ...prev,
                  sorts: removeSortRule(prev.sorts, propertyKey),
                }));
                onClose();
              }}
            >
              Remove sort
            </ContextMenuItem>
          )}
          <ContextMenuSeparator />
        </>
      )}
      {prop.groupable && (
        <>
          {config.groupBy !== propertyKey ? (
            <ContextMenuItem
              onClick={() => {
                onConfigChange((prev) => ({ ...prev, groupBy: propertyKey }));
                onClose();
              }}
            >
              Group by {prop.label}
            </ContextMenuItem>
          ) : (
            <ContextMenuItem
              onClick={() => {
                onConfigChange((prev) => ({ ...prev, groupBy: null }));
                onClose();
              }}
            >
              Remove grouping
            </ContextMenuItem>
          )}
          <ContextMenuSeparator />
        </>
      )}
      {canHideProperty(propertyKey) && (
        <ContextMenuItem
          onClick={() => {
            onConfigChange((prev) => hideProperty(prev, propertyKey));
            onClose();
          }}
        >
          Hide {prop.label}
        </ContextMenuItem>
      )}
      {hidden.length > 0 && (
        <>
          <ContextMenuSeparator />
          {hidden.map((hiddenProp) => (
            <ContextMenuItem
              key={hiddenProp.key}
              onClick={() => {
                onConfigChange((prev) => showProperty(prev, hiddenProp.key));
                onClose();
              }}
            >
              Show {hiddenProp.label}
            </ContextMenuItem>
          ))}
        </>
      )}
    </ContextMenu>
  );
}
