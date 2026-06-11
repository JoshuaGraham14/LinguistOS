"use client";

import {
  ArrowDownAZ,
  ArrowUpAZ,
  Eye,
  EyeOff,
  Layers,
  Layers2,
  ListX,
} from "lucide-react";
import { getVocabProperty } from "@/lib/vocab-properties";
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
  const isVisible = propertyKey
    ? config.visibleProperties.includes(propertyKey)
    : false;

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
    <ContextMenu open={open} x={x} y={y} onClose={onClose} minWidth={220}>
      {prop.sortable && (
        <>
          <ContextMenuItem
            icon={ArrowUpAZ}
            active={activeSort?.direction === "asc"}
            onClick={() => applySort("asc")}
          >
            Sort ascending
          </ContextMenuItem>
          <ContextMenuItem
            icon={ArrowDownAZ}
            active={activeSort?.direction === "desc"}
            onClick={() => applySort("desc")}
          >
            Sort descending
          </ContextMenuItem>
          {config.sorts.some((s) => s.field === propertyKey) && (
            <ContextMenuItem
              icon={ListX}
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
              icon={Layers}
              onClick={() => {
                onConfigChange((prev) => ({ ...prev, groupBy: propertyKey }));
                onClose();
              }}
            >
              Group by {prop.label}
            </ContextMenuItem>
          ) : (
            <ContextMenuItem
              icon={Layers2}
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
          icon={isVisible ? EyeOff : Eye}
          onClick={() => {
            onConfigChange((prev) =>
              isVisible
                ? hideProperty(prev, propertyKey)
                : showProperty(prev, propertyKey),
            );
            onClose();
          }}
        >
          {isVisible ? "Hide in view" : "Show in view"}
        </ContextMenuItem>
      )}
    </ContextMenu>
  );
}
