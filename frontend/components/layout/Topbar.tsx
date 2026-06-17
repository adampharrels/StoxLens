"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent } from "react";

export function Topbar() {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const ticker = String(form.get("ticker") ?? "").trim();
    if (ticker) router.push(`/research/${encodeURIComponent(ticker.toUpperCase())}`);
  }

  return (
    <header className="flex h-11 items-center border-b border-border bg-page px-4">
      <div className="w-[184px] shrink-0 text-base font-semibold">StoxLens</div>
      <form onSubmit={submit} className="relative max-w-[520px] flex-1">
        <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          name="ticker"
          aria-label="Ticker search"
          placeholder="Search ticker"
          className="h-7 w-full rounded-none border border-border bg-surface pl-8 pr-2 text-base text-primary placeholder:text-muted"
        />
      </form>
      <div className="ml-auto pl-4 text-xs text-muted">Last updated: today 09:14 AEST</div>
    </header>
  );
}
