"use client";

import { ArrowRight, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent } from "react";

export default function ResearchIndexPage() {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const ticker = String(form.get("ticker") ?? "").trim();
    if (ticker) router.push(`/research/${encodeURIComponent(ticker.toUpperCase())}`);
  }

  return (
    <div className="px-6 py-4">
      <div className="mb-4 text-lg font-medium">Research</div>
      <div className="max-w-[620px] border-t border-border pt-4">
        <div className="label mb-2">Ticker</div>
        <form onSubmit={submit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              name="ticker"
              aria-label="Ticker"
              placeholder="Enter ticker"
              className="h-8 w-full rounded-none border border-border bg-surface pl-8 pr-2 text-base text-primary placeholder:text-muted"
            />
          </div>
          <button type="submit" className="inline-flex h-8 items-center gap-2 border border-accent bg-accent px-3 text-sm text-white">
            Open
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
