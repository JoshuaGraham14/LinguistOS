"use client";

import {
  Calendar,
  CheckSquare,
  Eye,
  EyeOff,
  GripVertical,
  Hash,
  List,
  Tags,
  Type,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import {
  getVocabProperty,
  VOCAB_PROPERTIES,
  type PropertyType,
  type VocabPropertyDef,
} from "@/lib/vocab-properties";
import {
  canHideProperty,
  hideAllProperties,
  hideProperty,
  orderedPropertyKeys,
  reorderPropertyKeys,
  showAllProperties,
  showProperty,
  type VocabViewConfig,
} from "@/lib/vocab-view";

function PropertyTypeIcon({ type }: { type: PropertyType }) {
  const className = "h-4 w-4 shrink-0 text-slate-400";
  switch (type) {
    case "title":
    case "text":
      return <Type className={className} strokeWidth={2} />;
    case "select":
      return <List className={className} strokeWidth={2} />;
    case "multi_select":
      return <Tags className={className} strokeWidth={2} />;
    case "number":
      return <Hash className={className} strokeWidth={2} />;
    case "date":
      return <Calendar className={className} strokeWidth={2} />;
    case "checkbox":
      return <CheckSquare className={className} strokeWidth={2} />;
    default:
      return <Type className={className} strokeWidth={2} />;
  }
}

function PropertyRow({
  prop,
  visible,
  dragging,
  dragOver,
  onToggle,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: {
  prop: VocabPropertyDef;
  visible: boolean;
  dragging: boolean;
  dragOver: boolean;
  onToggle: () => void;
  onDragStart: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: () => void;
  onDragEnd: () => void;
}) {
  const locked = prop.isTitle === true;

  return (
    <div
      draggable={!locked}
      onDragStart={(e) => {
        if (locked) {
          e.preventDefault();
          return;
        }
        onDragStart();
      }}
      onDragOver={onDragOver}
      onDrop={(e) => {
        e.preventDefault();
        onDrop();
      }}
      onDragEnd={onDragEnd}
      className={cn(
        "flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-slate-700",
        dragOver && "bg-brand-50 ring-1 ring-brand-200",
        dragging && "opacity-50",
        !locked && "hover:bg-slate-50",
      )}
    >
      <GripVertical
        className={cn(
          "h-4 w-4 shrink-0",
          locked ? "text-slate-200" : "text-slate-300 cursor-grab active:cursor-grabbing",
        )}
      />
      <PropertyTypeIcon type={prop.type} />
      <span className="flex-1 truncate">{prop.label}</span>
      <button
        type="button"
        disabled={locked}
        onClick={onToggle}
        title={locked ? "Primary column is always visible" : visible ? "Hide" : "Show"}
        className={cn(
          "h-7 w-7 rounded-md flex items-center justify-center transition shrink-0",
          locked
            ? "text-slate-300 cursor-not-allowed"
            : visible
              ? "text-slate-700 hover:bg-slate-100"
              : "text-slate-400 hover:bg-slate-100 hover:text-slate-600",
        )}
      >
        {visible ? (
          <Eye className="h-4 w-4" strokeWidth={2} />
        ) : (
          <EyeOff className="h-4 w-4" strokeWidth={2} />
        )}
      </button>
    </div>
  );
}

export function PropertyVisibilityPopover({
  config,
  onConfigChange,
}: {
  config: VocabViewConfig;
  onConfigChange: (updater: (prev: VocabViewConfig) => VocabViewConfig) => void;
}) {
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);

  const orderedKeys = orderedPropertyKeys(config);
  const hideable = VOCAB_PROPERTIES.filter((p) => canHideProperty(p.key));
  const allHideableVisible = hideable.every((p) =>
    config.visibleProperties.includes(p.key),
  );

  function toggleProperty(key: string) {
    onConfigChange((prev) => {
      if (!canHideProperty(key)) return prev;
      return prev.visibleProperties.includes(key)
        ? hideProperty(prev, key)
        : showProperty(prev, key);
    });
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-2 pb-1 border-b border-slate-100">
        <span className="text-xs text-slate-500">Shown in table</span>
        <button
          type="button"
          onClick={() =>
            onConfigChange((prev) =>
              allHideableVisible
                ? hideAllProperties(prev)
                : showAllProperties(prev),
            )
          }
          className="text-xs font-medium text-brand-600 hover:text-brand-700"
        >
          {allHideableVisible ? "Hide all" : "Show all"}
        </button>
      </div>
      <div className="max-h-80 overflow-y-auto space-y-0.5">
        {orderedKeys.map((key) => {
          const prop = getVocabProperty(key);
          if (!prop) return null;
          const visible =
            config.visibleProperties.includes(key) || Boolean(prop.isTitle);
          return (
            <PropertyRow
              key={key}
              prop={prop}
              visible={visible}
              dragging={dragKey === key}
              dragOver={dragOverKey === key && dragKey !== key}
              onToggle={() => toggleProperty(key)}
              onDragStart={() => setDragKey(key)}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOverKey(key);
              }}
              onDrop={() => {
                if (dragKey) {
                  onConfigChange((prev) =>
                    reorderPropertyKeys(prev, dragKey, key),
                  );
                }
                setDragKey(null);
                setDragOverKey(null);
              }}
              onDragEnd={() => {
                setDragKey(null);
                setDragOverKey(null);
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
