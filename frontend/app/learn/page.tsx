"use client";

import {
  BookOpen,
  MessageSquare,
  Mic,
  Zap,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { cn } from "@/lib/cn";
import { useVocab } from "@/lib/storage";

type Color = "blue" | "green" | "purple" | "red";

const ICON_BG: Record<Color, string> = {
  blue: "bg-gradient-to-br from-blue-400 to-blue-600",
  green: "bg-gradient-to-br from-emerald-400 to-emerald-600",
  purple: "bg-gradient-to-br from-fuchsia-500 to-purple-600",
  red: "bg-gradient-to-br from-rose-400 to-rose-600",
};

const BUTTON_BG: Record<Color, string> = {
  blue: "bg-gradient-to-r from-blue-500 to-blue-600 hover:brightness-110",
  green: "bg-gradient-to-r from-emerald-500 to-emerald-600 hover:brightness-110",
  purple: "bg-btn-purple hover:brightness-110",
  red: "bg-gradient-to-r from-rose-500 to-rose-600 hover:brightness-110",
};

export default function LearnPage() {
  const { vocab, hydrated } = useVocab();

  const counts = useMemo(() => {
    const total = vocab.length;
    const verbs = vocab.filter((v) => v.tags.includes("verb")).length;
    return { total, verbs };
  }, [vocab]);

  const total = hydrated ? counts.total : 0;
  const verbs = hydrated ? counts.verbs : 0;

  const methods: {
    title: string;
    description: string;
    href: string;
    icon: LucideIcon;
    color: Color;
    cta: string;
    available: number;
    disabled?: boolean;
  }[] = [
    {
      title: "Flashcards",
      description: "Study words at your own pace",
      href: "/learn/flashcards",
      icon: BookOpen,
      color: "blue",
      cta: "Start Learning",
      available: total,
    },
    {
      title: "Voice Practice",
      description: "Practice pronunciation with speech recognition",
      href: "/learn/sentences?mode=voice",
      icon: Mic,
      color: "green",
      cta: "Start Voice",
      available: total,
    },
    {
      title: "Sentence Practice",
      description: "Learn words in context with sentences",
      href: "/learn/sentences",
      icon: MessageSquare,
      color: "purple",
      cta: "Start Sentences",
      available: total,
    },
    {
      title: "Verb Conjugation",
      description: "Master Spanish verb conjugations",
      href: "/learn",
      icon: Zap,
      color: "red",
      cta: "Coming soon",
      available: verbs,
      disabled: true,
    },
  ];

  return (
    <div className="space-y-8">
      <header className="text-left">
        <h1 className="text-3xl font-bold text-slate-900">Learn Spanish</h1>
        <p className="text-slate-500 mt-1">Choose your learning method</p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5 mx-auto w-full">
        {methods.map((m) => (
          <div
            key={m.title}
            className="glass-card rounded-2xl p-6 flex flex-col items-center text-center gap-4"
          >
            <div
              className={cn(
                "h-16 w-16 rounded-2xl flex items-center justify-center shadow-md",
                ICON_BG[m.color],
              )}
            >
              <m.icon className="h-8 w-8 text-white" strokeWidth={2} />
            </div>
            <h2 className="text-xl font-bold text-slate-900">{m.title}</h2>
            <p className="text-slate-500 text-sm">{m.description}</p>
            <div className="flex items-center gap-2 text-sm text-slate-500 mt-2">
              <BookOpen className="h-4 w-4" strokeWidth={2} />
              {m.available} words available
            </div>
            {m.disabled ? (
              <button
                type="button"
                disabled
                className="w-full rounded-xl bg-slate-200 text-slate-500 font-medium py-3 cursor-not-allowed"
              >
                {m.cta}
              </button>
            ) : (
              <Link
                href={m.href}
                className={cn(
                  "w-full rounded-xl text-white font-medium py-3 text-center shadow-soft transition",
                  BUTTON_BG[m.color],
                )}
              >
                {m.cta}
              </Link>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
