"use client";

import {
  BookMarked,
  BookOpen,
  CircleSlash,
  MessageSquare,
  Target,
  Wand2,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { QuickActionCard } from "@/components/QuickActionCard";
import { StatCard } from "@/components/StatCard";
import { useProfile, useVocab } from "@/lib/storage";

export default function DashboardPage() {
  const { vocab, hydrated } = useVocab();
  const { profile, hydrated: profileHydrated } = useProfile();

  const stats = useMemo(() => {
    const total = vocab.length;
    const learned = vocab.filter((v) => v.learned).length;
    const remaining = total - learned;
    return { total, learned, remaining };
  }, [vocab]);

  const greetingName =
    profileHydrated && profile.name.trim() ? profile.name.trim() : null;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-slate-900">
          {greetingName ? `Hello, ${greetingName}!` : "Welcome to LinguistOS"}
        </h1>
        <p className="text-slate-500 mt-1">
          {greetingName
            ? "Ready to learn Spanish today?"
            : "Set your name in Settings to personalise this view."}
        </p>
      </header>

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          icon={BookOpen}
          value={hydrated ? String(stats.total) : "—"}
          label="Total Words"
          color="blue"
        />
        <StatCard
          icon={Target}
          value={hydrated ? String(stats.learned) : "—"}
          label="Words Learned"
          color="green"
        />
        <StatCard
          icon={CircleSlash}
          value={hydrated ? String(stats.remaining) : "—"}
          label="Still Learning"
          color="purple"
        />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 glass-card rounded-2xl p-12 flex flex-col items-center justify-center min-h-[320px]">
          <h2 className="text-2xl font-bold text-slate-900">Ready to practice?</h2>
          <p className="text-slate-500 mt-2 text-center max-w-md">
            Pick a learning method, or jump straight into a generated sentence
            for any word in your collection.
          </p>
          <Link
            href="/learn"
            className="mt-8 inline-flex items-center gap-2 bg-btn-purple text-white font-medium rounded-full px-6 py-3 shadow-card transition hover:brightness-110"
          >
            <Wand2 className="h-4 w-4" strokeWidth={2} />
            Start learning
          </Link>
        </div>

        <div className="glass-card rounded-2xl p-6">
          <h3 className="font-bold text-slate-900 mb-4">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-3">
            <QuickActionCard
              href="/learn/flashcards"
              label="Flashcards"
              icon={BookOpen}
              color="blue"
            />
            <QuickActionCard
              href="/learn/sentences"
              label="Sentences"
              icon={MessageSquare}
              color="purple"
            />
            <QuickActionCard
              href="/learn"
              label="All modes"
              icon={Zap}
              color="red"
            />
            <QuickActionCard
              href="/vocab"
              label="Vocabulary"
              icon={BookMarked}
              color="green"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
