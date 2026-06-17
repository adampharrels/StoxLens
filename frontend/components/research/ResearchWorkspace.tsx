"use client";

import { useState } from "react";
import { AIBrief } from "@/components/research/AIBrief";
import { CompanyRow } from "@/components/research/CompanyRow";
import { HistoryTable } from "@/components/research/HistoryTable";
import { MetricsTable } from "@/components/research/MetricsTable";
import { PriceChart } from "@/components/research/PriceChart";
import { SignalScores } from "@/components/research/SignalScores";
import { ResearchTab, Tabs } from "@/components/research/Tabs";
import type { ResearchResponse } from "@/lib/types";

export function ResearchWorkspace({ data }: { data: ResearchResponse }) {
  const [tab, setTab] = useState<ResearchTab>("Overview");
  const overall = data.latest_report?.overall_view ?? "Needs Review";

  return (
    <div className="px-6 pb-8">
      <CompanyRow
        companyName={data.company_name}
        ticker={data.ticker}
        exchange={data.exchange}
        sector={data.sector}
        price={data.price}
        priceChangePct={data.price_change_pct}
      />
      <Tabs active={tab} onChange={setTab} />
      {tab === "Overview" && (
        <>
          <MetricsTable signals={data.signals} />
          <PriceChart data={data.price_history} />
        </>
      )}
      {tab === "Signals" && <SignalScores signals={data.signals} overall={overall} />}
      {tab === "AI Brief" && <AIBrief report={data.latest_report} ticker={data.ticker} />}
      {tab === "History" && <HistoryTable data={data.price_history} />}
    </div>
  );
}
