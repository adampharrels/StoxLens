"use client";

import { FormEvent, useState, useTransition } from "react";
import Link from "next/link";
import { ArrowRight, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { addWatchlistItem, removeWatchlistItem, updateWatchlistItem } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";

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
  const [editValue, setEditValue] = useState("");
  const [isPending, startTransition] = useTransition();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const ticker = String(data.get("ticker") ?? "").trim().toUpperCase();
    if (!ticker) return;

    setError(null);
    setPendingTicker(ticker);
    startTransition(async () => {
      try {
        const item = await addWatchlistItem(ticker);
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
    setEditingTicker(ticker);
    setEditValue(ticker);
    setError(null);
  }

  function cancelEdit() {
    setEditingTicker(null);
    setEditValue("");
  }

  function saveEdit(ticker: string) {
    const replacement = editValue.trim().toUpperCase();
    if (!replacement) return;

    setError(null);
    setPendingTicker(ticker);
    startTransition(async () => {
      try {
        const item = await updateWatchlistItem(ticker, replacement);
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
      <form onSubmit={submit} className="flex max-w-[460px] gap-2">
        <input
          name="ticker"
          aria-label="Ticker"
          placeholder="Add ticker"
          className="h-8 flex-1 rounded-none border border-border bg-surface px-2 text-base text-primary placeholder:text-muted"
        />
        <button
          type="submit"
          disabled={isPending}
          className="inline-flex h-8 items-center gap-2 border border-accent bg-accent px-3 text-sm text-white disabled:opacity-60"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </form>

      {error && <div className="mt-3 text-sm text-red-600">{error}</div>}

      <div className="mt-6 border-t border-border">
        {items.length > 0 ? (
          items.map((item) => (
            <div key={item.ticker} className="grid grid-cols-[110px_1fr_120px_120px] items-center gap-4 border-b border-border py-3">
              {editingTicker === item.ticker ? (
                <input
                  aria-label={`Edit ${item.ticker}`}
                  value={editValue}
                  onChange={(event) => setEditValue(event.target.value.toUpperCase())}
                  className="h-7 w-full rounded-none border border-border bg-surface px-2 font-mono text-base text-primary"
                />
              ) : (
                <Link href={`/research/${item.ticker}`} prefetch={false} className="font-mono text-base font-medium hover:underline">
                  {item.ticker}
                </Link>
              )}
              <div className="text-sm text-secondary">{item.signal}</div>
              <div className="text-xs text-muted">{addedLabel(item.created_at)}</div>
              <div className="flex justify-end gap-2">
                {editingTicker === item.ticker ? (
                  <>
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
                  </>
                ) : (
                  <>
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
                  </>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="py-8 text-sm text-secondary">No saved tickers yet.</div>
        )}
      </div>
    </div>
  );
}
