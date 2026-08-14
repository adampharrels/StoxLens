"use client";

import { FormEvent, useState, useTransition } from "react";
import Link from "next/link";
import { ArrowRight, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { addWatchlistItem, removeWatchlistItem, updateWatchlistItem } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";

type WatchlistDraft = Pick<WatchlistItem, "ticker" | "watch_reason" | "main_risk" | "change_my_mind">;

function addedLabel(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function WatchlistManager({ initialItems }: { initialItems: WatchlistItem[] }) {
  const [items, setItems] = useState(initialItems);
  const [error, setError] = useState<string | null>(null);
  const [pendingTicker, setPendingTicker] = useState<string | null>(null);
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<WatchlistDraft | null>(null);
  const [isPending, startTransition] = useTransition();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const ticker = String(data.get("ticker") ?? "").trim().toUpperCase();
    if (!ticker) return;
    const payload = {
      ticker,
      watch_reason: String(data.get("watch_reason") ?? "").trim(),
      main_risk: String(data.get("main_risk") ?? "").trim(),
      change_my_mind: String(data.get("change_my_mind") ?? "").trim()
    };

    setError(null);
    setPendingTicker(ticker);
    startTransition(async () => {
      try {
        const item = await addWatchlistItem(payload);
        setItems((current) => {
          const withoutExisting = current.filter((entry) => entry.ticker !== item.ticker);
          return [...withoutExisting, item].sort((left, right) => left.ticker.localeCompare(right.ticker));
        });
        form.reset();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not add ticker.");
      } finally {
        setPendingTicker(null);
      }
    });
  }

  function remove(ticker: string) {
    setError(null);
    setPendingTicker(ticker);
    startTransition(async () => {
      try {
        await removeWatchlistItem(ticker);
        setItems((current) => current.filter((item) => item.ticker !== ticker));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not remove ticker.");
      } finally {
        setPendingTicker(null);
      }
    });
  }

  function beginEdit(ticker: string) {
    const item = items.find((entry) => entry.ticker === ticker);
    if (!item) return;
    setEditingTicker(ticker);
    setEditDraft({
      ticker: item.ticker,
      watch_reason: item.watch_reason,
      main_risk: item.main_risk,
      change_my_mind: item.change_my_mind
    });
    setError(null);
  }

  function cancelEdit() {
    setEditingTicker(null);
    setEditDraft(null);
  }

  function saveEdit(ticker: string) {
    if (!editDraft) return;

    const payload = {
      ticker: editDraft.ticker.trim().toUpperCase(),
      watch_reason: editDraft.watch_reason.trim(),
      main_risk: editDraft.main_risk.trim(),
      change_my_mind: editDraft.change_my_mind.trim()
    };
    if (!payload.ticker) return;

    setError(null);
    setPendingTicker(ticker);
    startTransition(async () => {
      try {
        const item = await updateWatchlistItem(ticker, payload);
        setItems((current) => {
          const withoutOld = current.filter((entry) => entry.ticker !== ticker && entry.ticker !== item.ticker);
          return [...withoutOld, item].sort((left, right) => left.ticker.localeCompare(right.ticker));
        });
        cancelEdit();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not update ticker.");
      } finally {
        setPendingTicker(null);
      }
    });
  }

  return (
    <div>
      <form onSubmit={submit} className="max-w-[820px] border-t border-border pt-4">
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <label className="label pt-2" htmlFor="ticker">Ticker</label>
          <input
            id="ticker"
            name="ticker"
            aria-label="Ticker"
            placeholder="MSFT"
            className="h-8 w-full rounded-none border border-border bg-surface px-2 text-base text-primary placeholder:text-muted"
          />

          <label className="label pt-2" htmlFor="watch_reason">Watch reason</label>
          <textarea
            id="watch_reason"
            name="watch_reason"
            rows={2}
            placeholder="Azure growth and AI infrastructure demand."
            className="min-h-16 w-full resize-y rounded-none border border-border bg-surface px-2 py-1 text-sm text-primary placeholder:text-muted"
          />

          <label className="label pt-2" htmlFor="main_risk">Main risk</label>
          <textarea
            id="main_risk"
            name="main_risk"
            rows={2}
            placeholder="Valuation is expensive."
            className="min-h-16 w-full resize-y rounded-none border border-border bg-surface px-2 py-1 text-sm text-primary placeholder:text-muted"
          />

          <label className="label pt-2" htmlFor="change_my_mind">Change my mind</label>
          <textarea
            id="change_my_mind"
            name="change_my_mind"
            rows={2}
            placeholder="Cloud growth slows or margins weaken."
            className="min-h-16 w-full resize-y rounded-none border border-border bg-surface px-2 py-1 text-sm text-primary placeholder:text-muted"
          />
        </div>

        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={isPending}
            className="inline-flex h-8 items-center gap-2 border border-accent bg-accent px-3 text-sm text-white disabled:opacity-60"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        </div>
      </form>

      {error && <div className="mt-3 text-sm text-red-600">{error}</div>}

      <div className="mt-6 border-t border-border">
        {items.length > 0 ? (
          items.map((item) => (
            <div key={item.ticker} className="border-b border-border py-4">
              {editingTicker === item.ticker ? (
                <div className="grid grid-cols-[110px_1fr_120px] gap-4">
                  <input
                    aria-label={`Edit ${item.ticker}`}
                    value={editDraft?.ticker ?? ""}
                    onChange={(event) => setEditDraft((current) => current ? { ...current, ticker: event.target.value.toUpperCase() } : current)}
                    className="h-8 w-full rounded-none border border-border bg-surface px-2 font-mono text-base text-primary"
                  />
                  <div className="grid grid-cols-3 gap-3">
                    <textarea
                      aria-label="Edit watch reason"
                      value={editDraft?.watch_reason ?? ""}
                      onChange={(event) => setEditDraft((current) => current ? { ...current, watch_reason: event.target.value } : current)}
                      rows={3}
                      className="min-h-20 resize-y rounded-none border border-border bg-surface px-2 py-1 text-sm text-primary"
                    />
                    <textarea
                      aria-label="Edit main risk"
                      value={editDraft?.main_risk ?? ""}
                      onChange={(event) => setEditDraft((current) => current ? { ...current, main_risk: event.target.value } : current)}
                      rows={3}
                      className="min-h-20 resize-y rounded-none border border-border bg-surface px-2 py-1 text-sm text-primary"
                    />
                    <textarea
                      aria-label="Edit change my mind"
                      value={editDraft?.change_my_mind ?? ""}
                      onChange={(event) => setEditDraft((current) => current ? { ...current, change_my_mind: event.target.value } : current)}
                      rows={3}
                      className="min-h-20 resize-y rounded-none border border-border bg-surface px-2 py-1 text-sm text-primary"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      disabled={pendingTicker === item.ticker}
                      onClick={() => saveEdit(item.ticker)}
                      className="inline-flex h-7 w-7 items-center justify-center border border-border hover:bg-subtle disabled:opacity-60"
                      title="Save"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                    <button type="button" onClick={cancelEdit} className="inline-flex h-7 w-7 items-center justify-center border border-border hover:bg-subtle" title="Cancel">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-[110px_1fr_120px_120px] items-start gap-4">
                  <div>
                    <Link href={`/research/${item.ticker}`} prefetch={false} className="font-mono text-base font-medium hover:underline">
                      {item.ticker}
                    </Link>
                    <div className="mt-1 text-xs text-muted">{addedLabel(item.created_at)}</div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <div className="label mb-1">Watch reason</div>
                      <div className="text-secondary">{item.watch_reason || "Not set."}</div>
                    </div>
                    <div>
                      <div className="label mb-1">Main risk</div>
                      <div className="text-secondary">{item.main_risk || "Not set."}</div>
                    </div>
                    <div>
                      <div className="label mb-1">Change my mind</div>
                      <div className="text-secondary">{item.change_my_mind || "Not set."}</div>
                    </div>
                  </div>
                  <div className="text-sm text-secondary">{item.signal}</div>
                  <div className="flex justify-end gap-2">
                    <Link href={`/research/${item.ticker}`} prefetch={false} className="inline-flex h-7 w-7 items-center justify-center border border-border hover:bg-subtle" title="Open research">
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                    <button type="button" onClick={() => beginEdit(item.ticker)} className="inline-flex h-7 w-7 items-center justify-center border border-border hover:bg-subtle" title="Edit">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      disabled={pendingTicker === item.ticker}
                      onClick={() => remove(item.ticker)}
                      className="inline-flex h-7 w-7 items-center justify-center border border-border hover:bg-subtle disabled:opacity-60"
                      title="Remove"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="py-8 text-sm text-secondary">No saved tickers yet.</div>
        )}
      </div>
    </div>
  );
}
