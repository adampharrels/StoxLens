"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getWatchlist } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";

const nav = [
  { href: "/", label: "Home" },
  { href: "/today", label: "Today" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/research", label: "Research" },
  { href: "/compare", label: "Compare" },
  { href: "/reports", label: "Reports" }
];

export function Sidebar() {
  const pathname = usePathname();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);

  useEffect(() => {
    getWatchlist()
      .then(setWatchlist)
      .catch(() => setWatchlist([]));
  }, []);

  return (
    <aside className="h-full w-[200px] shrink-0 border-r border-border bg-page py-3">
      <nav className="space-y-1">
        {nav.map((item) => {
          const section = item.href.split("/")[1];
          const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`/${section}`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block border-l-2 px-3 py-2 text-sm ${
                active ? "border-accent bg-subtle text-primary" : "border-transparent text-secondary"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-7 px-3">
        <Link href="/watchlist" className="label mb-2 block hover:underline">
          Watchlist
        </Link>
        <div className="space-y-1">
          {watchlist.length > 0 ? (
            watchlist.map((item) => (
              <Link key={item.ticker} href={`/research/${item.ticker}`} className="flex justify-between py-1 text-xs hover:underline">
                <span className="font-mono text-sm">{item.ticker}</span>
                <span className="text-xs text-secondary">{item.signal}</span>
              </Link>
            ))
          ) : (
            <Link href="/watchlist" className="block py-1 text-xs text-muted hover:underline">
              Add tickers
            </Link>
          )}
        </div>
      </div>
    </aside>
  );
}
