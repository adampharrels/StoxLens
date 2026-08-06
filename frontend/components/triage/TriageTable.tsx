import Link from "next/link";
import { ArrowRight, AlertTriangle, CircleCheck, CircleDot } from "lucide-react";
import { fmtPct } from "@/lib/format";
import type { TriageItem } from "@/lib/types";

const severityStyle: Record<TriageItem["severity"], string> = {
  High: "text-red-600",
  Medium: "text-amber-600",
  Low: "text-secondary"
};

const severityIcon = {
  High: AlertTriangle,
  Medium: CircleDot,
  Low: CircleCheck
};

function metricLabel(item: TriageItem) {
  const rsi = Number(item.metrics.rsi);
  const vol = Number(item.metrics.volatility_percentile);
  const volume = Number(item.metrics.volume_ratio);
  return `RSI ${rsi.toFixed(1)} · Vol pct ${(vol * 100).toFixed(0)} · Volume ${volume.toFixed(1)}x`;
}

export function TriageTable({ items }: { items: TriageItem[] }) {
  if (items.length === 0) {
    return (
      <div className="border-t border-border py-8 text-sm text-secondary">
        No watchlist tickers need attention from the current data set.
      </div>
    );
  }

  return (
    <div className="border-t border-border">
      {items.map((item) => {
        const Icon = severityIcon[item.severity];
        const topReasons = item.reasons.slice(0, 3);
        return (
          <div key={item.ticker} className="grid grid-cols-[92px_110px_1fr_90px] gap-4 border-b border-border py-4">
            <div>
              <Link href={`/research/${item.ticker}`} prefetch={false} className="font-mono text-base font-medium hover:underline">
                {item.ticker}
              </Link>
              <div className="mt-1 numeric text-xs text-muted">${item.price.toFixed(2)}</div>
            </div>

            <div>
              <div className={`inline-flex items-center gap-1 text-sm font-medium ${severityStyle[item.severity]}`}>
                <Icon className="h-4 w-4" />
                {item.severity}
              </div>
              <div className="mt-1 numeric text-xs text-muted">Score {item.attention_score}/100</div>
              <div className="mt-1 numeric text-xs text-muted">{fmtPct(item.price_change_pct)}</div>
            </div>

            <div>
              <div className="space-y-1">
                {topReasons.length > 0 ? (
                  topReasons.map((reason) => (
                    <div key={reason.code} className="text-sm">
                      <span className="font-medium text-primary">{reason.label}</span>
                      <span className="text-secondary"> · {reason.detail}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-secondary">Signals are stable. No material threshold crossed.</div>
                )}
              </div>
              <div className="mt-2 text-xs text-muted">{metricLabel(item)}</div>
            </div>

            <div className="flex items-start justify-end">
              <Link href={`/research/${item.ticker}`} prefetch={false} className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
                Open
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}
