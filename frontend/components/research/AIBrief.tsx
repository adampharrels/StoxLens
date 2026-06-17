"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { generateResearch } from "@/lib/api";
import { overallViewColor } from "@/lib/format";
import type { ResearchReport } from "@/lib/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <div className="mb-2 text-xs uppercase tracking-[0.08em] text-muted">{title}</div>
      <div className="leading-[1.6]">{children}</div>
    </section>
  );
}

export function AIBrief({ report, ticker }: { report: ResearchReport | null; ticker: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function regenerate() {
    setBusy(true);
    await generateResearch(ticker);
    setBusy(false);
    router.refresh();
  }

  if (!report) {
    return (
      <div className="py-4">
        <button onClick={regenerate} className="inline-flex items-center gap-2 border border-border bg-transparent px-2 py-1 text-sm">
          <RefreshCw className="h-4 w-4" />
          Generate brief
        </button>
      </div>
    );
  }

  const list = (items: string[]) => (
    <div className="space-y-1">
      {items.map((item) => (
        <div key={item}>— {item}</div>
      ))}
    </div>
  );

  return (
    <div className="max-w-[760px] py-4">
      <div className="flex items-center gap-4 text-sm">
        <button
          onClick={regenerate}
          disabled={busy}
          className="inline-flex items-center gap-2 border border-border bg-transparent px-2 py-1 text-sm disabled:text-muted"
        >
          <RefreshCw className="h-4 w-4" />
          {busy ? "Regenerating" : "Regenerate brief"}
        </button>
        <span className="text-muted">Prompt {report.prompt_version}</span>
        <span className="text-muted">Generated: today 09:14</span>
      </div>
      <Section title="Summary">{report.summary}</Section>
      <Section title="Positive Signals">{list(report.positive_signals)}</Section>
      <Section title="Risks">{list(report.risks)}</Section>
      <Section title="Data Quality Notes">{list(report.data_quality_notes)}</Section>
      <Section title="Questions For Analyst">{list(report.questions_for_research)}</Section>
      <div className="mt-5">
        RESEARCH VIEW: <span style={{ color: overallViewColor(report.overall_view) }}>{report.overall_view}</span>
      </div>
    </div>
  );
}
