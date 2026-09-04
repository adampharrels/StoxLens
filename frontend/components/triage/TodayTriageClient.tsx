"use client";

import { useState } from "react";
import { TriageLegend } from "@/components/triage/TriageLegend";
import { TriageTable } from "@/components/triage/TriageTable";
import { runTriage } from "@/lib/api";
import type { TriageResponse } from "@/lib/types";

function generatedLabel(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function attentionCounts(data: TriageResponse) {
  return {
    high: data.items.filter((item) => item.status === "ok" && item.severity === "High").length,
    medium: data.items.filter((item) => item.status === "ok" && item.severity === "Medium").length
  };
}

export function TodayTriageClient({ initialData }: { initialData: TriageResponse }) {
  const [data, setData] = useState(initialData);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const counts = attentionCounts(data);

  async function onRunCheck() {
    setIsRunning(true);
    setRunError(null);
    try {
      const nextData = await runTriage();
      setData(nextData);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Run Check failed. Try again.");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="px-6 py-4">
      <div className="border-b border-border pb-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-lg font-medium">Today</div>
            <div className="mt-1 max-w-[620px] text-sm leading-6 text-secondary">
              Latest saved watchlist triage, sorted by attention urgency.
            </div>
          </div>
          <div className="flex items-center gap-3">
            {runError && (
              <div className="max-w-[360px] text-right text-xs text-red-600" role="alert">
                {runError}
              </div>
            )}
            <button
              className="h-8 border border-border px-3 text-sm text-primary hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isRunning}
              onClick={onRunCheck}
              type="button"
            >
              {isRunning ? "Running..." : "Run check"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid max-w-[820px] grid-cols-3 gap-6 py-5">
        <div>
          <div className="label">High</div>
          <div className="mt-1 numeric text-xl">{counts.high}</div>
        </div>
        <div>
          <div className="label">Medium</div>
          <div className="mt-1 numeric text-xl">{counts.medium}</div>
        </div>
        <div>
          <div className="label">Generated</div>
          <div className="mt-1 text-sm">{generatedLabel(data.generated_at)}</div>
        </div>
      </div>

      <TriageLegend />
      <TriageTable items={data.items} />
    </div>
  );
}
