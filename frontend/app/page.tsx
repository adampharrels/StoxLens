"use client";

import { ArrowRight, FileText, Search, Table2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent } from "react";
import { starterTickers } from "@/lib/tickers";

const workflow = [
  {
    label: "Research",
    href: "/research",
    icon: Search,
    text: "Generate a quantitative research view for a ticker."
  },
  {
    label: "Compare",
    href: "/compare",
    icon: Table2,
    text: "Review signal metrics across multiple equities."
  },
  {
    label: "Reports",
    href: "/reports",
    icon: FileText,
    text: "Open generated research notes and report history."
  }
];

export default function Home() {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const ticker = String(form.get("ticker") ?? "").trim();
    if (ticker) router.push(`/research/${encodeURIComponent(ticker.toUpperCase())}`);
  }

  return (
    <div className="px-6 py-4">
      <div className="border-b border-border pb-4">
        <div className="text-lg font-medium">StoxLens</div>
        <div className="mt-1 max-w-[680px] text-sm leading-6 text-secondary">
          Equity research workspace for price history, signal scoring, generated briefs, comparisons, and report review.
        </div>
      </div>

      <div className="grid max-w-[920px] grid-cols-[minmax(0,1fr)_260px] gap-8 py-5">
        <section>
          <div className="label mb-2">Start Research</div>
          <form onSubmit={submit} className="flex max-w-[520px] gap-2">
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

          <div className="mt-3 flex max-w-[520px] flex-wrap gap-2">
            {starterTickers.map((ticker) => (
              <Link key={ticker} href={`/research/${ticker}`} prefetch={false} className="border border-border px-2 py-1 font-mono text-xs hover:bg-subtle">
                {ticker}
              </Link>
            ))}
          </div>

          <div className="mt-7">
            <div className="label mb-2">Workspace</div>
            <div className="border-t border-border">
              {workflow.map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.href} href={item.href} prefetch={false} className="grid grid-cols-[120px_1fr_20px] items-center border-b border-border py-3 hover:bg-subtle">
                    <span className="inline-flex items-center gap-2 text-sm font-medium">
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </span>
                    <span className="text-sm text-secondary">{item.text}</span>
                    <ArrowRight className="h-4 w-4 text-muted" />
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        <aside>
          <div className="label mb-2">System</div>
          <div className="border-t border-border">
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span className="text-secondary">Backend</span>
              <span>FastAPI :8000</span>
            </div>
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span className="text-secondary">Frontend</span>
              <span>Next.js :3000</span>
            </div>
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span className="text-secondary">Data</span>
              <span>Alpha Vantage</span>
            </div>
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span className="text-secondary">Prompt</span>
              <span>v2.1</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
