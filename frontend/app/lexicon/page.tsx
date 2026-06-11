"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import {
  isEmptyLexiconQuery,
  parseLexiconQuery,
  serializeLexiconQuery,
} from "@/lib/lexicon-query";

function LexiconRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const query = parseLexiconQuery(searchParams.toString());
    const params = new URLSearchParams();
    const view = searchParams.get("view");
    if (view) params.set("view", view);
    if (!isEmptyLexiconQuery(query)) {
      params.set("filter", serializeLexiconQuery(query));
    }
    const qs = params.toString();
    router.replace(qs ? `/vocab?${qs}` : "/vocab");
  }, [router, searchParams]);

  return <div className="text-slate-400 text-center py-12">Redirecting…</div>;
}

export default function LexiconRedirectPage() {
  return (
    <Suspense fallback={<div className="text-slate-400 text-center py-12">Loading…</div>}>
      <LexiconRedirectInner />
    </Suspense>
  );
}
