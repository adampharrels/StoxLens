"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getWatchlist } from "@/lib/api";

const nav = [
  { href: "/", label: "Home" },
  { href: "/research", label: "Research" },
  { href: "/compare", label: "Compare" },
  { href: "/reports", label: "Reports" }
];

export function Sidebar() {
  const pathname = usePathname();
  const [watchlist, setWatchlist] = useState<{ ticker: string; signal: string }[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getWatchlist()
      .then(setWatchlist)
      .catch(() => setWatchlist([]))
      .finally(() => setLoaded(true));
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
        <div className="label mb-2">Watchlist</div>
        <div className="space-y-1">
          {watchlist.length > 0 &&
            watchlist.map((item) => (
              <Link key={item.ticker} href={`/research/${item.ticker}`} className="flex justify-between py-1 text-xs hover:underline">
                <span className="font-mono text-sm">{item.ticker}</span>
                <span className="text-xs text-secondary">{item.signal}</span>
              </Link>
            ))}
          {loaded && watchlist.length === 0 && <div className="py-1 text-xs text-muted">No watchlist loaded</div>}
        </div>
      </div>
    </aside>
  );
}
