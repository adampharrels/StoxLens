import Link from "next/link";
import { AlertTriangle, CircleCheck, CircleDot } from "lucide-react";
import { fmtPct } from "@/lib/format";
import type { TriageItem, WatchNote } from "@/lib/types";

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

function newsLabel(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function contribution(impact: number) {
  return `+${impact * 12}`;
}

function sentence(value: string) {
  return value.trim().replace(/\.$/, "");
}

function primaryAlert(item: TriageItem) {
  const reason = item.reasons[0];
  return reason ? `${reason.label}: ${reason.detail}` : "Signals are stable. No material threshold crossed.";
}

const emptyWatchNote: WatchNote = {
  ticker: "",
  watch_reason: "",
  main_risk: "",
  change_my_mind: ""
};

function researchQuestion(item: TriageItem, note: WatchNote) {
  const change = sentence(note.change_my_mind);
  const reason = sentence(note.watch_reason);
  if (change) {
    return `Is this alert evidence that ${change.toLowerCase()}?`;
  }
  if (reason) {
    return `Is this temporary noise, or is ${reason.toLowerCase()} changing?`;
  }
  return `Does this alert change the reason to keep watching ${item.ticker}?`;
}

function scoreDelta(value: number) {
  if (value > 0) return `+${value}`;
  return String(value);
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
        const watchNote = item.watch_note ?? emptyWatchNote;
        const hasWatchNote = Boolean(watchNote.watch_reason || watchNote.main_risk || watchNote.change_my_mind);
        return (
          <div key={item.ticker} className="grid grid-cols-[92px_110px_minmax(0,1fr)] gap-4 border-b border-border py-4">
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
              {hasWatchNote && (
                <div className="mb-3 grid grid-cols-[130px_1fr] gap-x-3 gap-y-1 border-b border-border pb-3 text-sm">
                  {watchNote.watch_reason && (
                    <>
                      <div className="label">Why watching</div>
                      <div className="text-secondary">{watchNote.watch_reason}</div>
                    </>
                  )}
                  {watchNote.main_risk && (
                    <>
                      <div className="label">Main risk</div>
                      <div className="text-secondary">{watchNote.main_risk}</div>
                    </>
                  )}
                  {watchNote.change_my_mind && (
                    <>
                      <div className="label">Change my mind</div>
                      <div className="text-secondary">{watchNote.change_my_mind}</div>
                    </>
                  )}
                  <div className="label">Today's alert</div>
                  <div className="text-secondary">{primaryAlert(item)}</div>
                  <div className="label">Research question</div>
                  <div className="text-secondary">{researchQuestion(item, watchNote)}</div>
                </div>
              )}
              {item.changes && (
                <div className="mb-3 border-b border-border pb-3">
                  <div className="mb-1 flex items-center gap-2 text-sm font-medium">
                    <span>What changed since last check</span>
                    {item.changes.previous_severity && (
                      <span className="numeric text-xs text-muted">
                        {item.changes.previous_severity} to {item.severity} · {scoreDelta(item.changes.score_delta)}
                      </span>
                    )}
                  </div>
                  <ul className="space-y-1 text-sm text-secondary">
                    {item.changes.details.slice(0, 4).map((detail) => (
                      <li key={detail}>- {detail}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="space-y-1">
                {topReasons.length > 0 ? (
                  topReasons.map((reason) => (
                    <div key={reason.code} className="flex gap-2 text-sm">
                      <span className="numeric w-9 shrink-0 text-muted">{contribution(reason.impact)}</span>
                      <span>
                        <span className="font-medium text-primary">{reason.label}</span>
                        <span className="text-secondary"> · {reason.detail}</span>
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-secondary">Signals are stable. No material threshold crossed.</div>
                )}
              </div>
              <div className="mt-2 text-xs text-muted">{metricLabel(item)}</div>
              {item.news.length > 0 && (
                <div className="mt-3 space-y-1 border-t border-border pt-2">
                  {item.news.slice(0, 2).map((article) => (
                    <a
                      key={`${article.title}-${article.published_at}`}
                      href={article.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block text-xs hover:underline"
                    >
                      <span className="font-medium text-primary">{article.category}</span>
                      <span className="text-secondary"> · {article.title}</span>
                      <span className="text-muted"> · {article.source}, {newsLabel(article.published_at)}</span>
                    </a>
                  ))}
                </div>
              )}
            </div>

          </div>
        );
      })}
    </div>
  );
}
