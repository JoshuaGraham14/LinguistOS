"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

function WordsRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("layout", "gallery");
    router.replace(`/vocab?${params.toString()}`);
  }, [router, searchParams]);

  return <div className="text-slate-400 text-center py-12">Redirecting…</div>;
}

export default function WordsRedirectPage() {
  return (
    <Suspense fallback={<div className="text-slate-400 text-center py-12">Loading…</div>}>
      <WordsRedirectInner />
    </Suspense>
  );
}
