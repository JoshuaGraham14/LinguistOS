"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

function LexiconRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("q");
    params.delete("tags");
    params.delete("pos");
    params.delete("cefr");
    params.delete("learned");
    params.delete("due");
    params.delete("box_min");
    params.delete("box_max");
    params.delete("lang");
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
