"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AIBrief } from "@/components/research/AIBrief";
import { CompanyRow } from "@/components/research/CompanyRow";
import { FundamentalsPanel } from "@/components/research/FundamentalsPanel";
import { HistoryTable } from "@/components/research/HistoryTable";
import { MetricsTable } from "@/components/research/MetricsTable";
import { PriceChart } from "@/components/research/PriceChart";
import { SignalScores } from "@/components/research/SignalScores";
import { ResearchTab, Tabs } from "@/components/research/Tabs";
import type { PricePoint, ResearchResponse } from "@/lib/types";
import { runResearch } from "@/lib/api";

export function ResearchWorkspace({ data, chartData }: { data: ResearchResponse; chartData: PricePoint[] }) {
  const [tab, setTab] = useState<ResearchTab>("Overview");
  const [isRunning, setIsRunning] = useState(false);
  const [currentData, setCurrentData] = useState(data);
  const [currentChartData, setCurrentChartData] = useState(chartData.length > 0 ? chartData : data.price_history);
  const router = useRouter();
  const overall = currentData.latest_report?.overall_view ?? "Needs Review";

  useEffect(() => {
    // Keep client state aligned when navigating from one ticker page to another.
    setCurrentData(data);
    setCurrentChartData(chartData.length > 0 ? chartData : data.price_history);
  }, [data, chartData]);

  async function onRunCheck() {
    setIsRunning(true);
    try {
      // Use the response immediately so the user sees new candles without needing a second click.
      const nextData = await runResearch(currentData.ticker);
      setCurrentData(nextData);
      setCurrentChartData(nextData.price_history);
      router.refresh();
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="px-6 pb-8">
      <CompanyRow
        companyName={currentData.company_name}
        ticker={currentData.ticker}
        exchange={currentData.exchange}
        sector={currentData.sector}
        price={currentData.price}
        priceChangePct={currentData.price_change_pct}
      />
      <div className="mb-3 flex items-center justify-between border-b border-border pb-3">
        <div className="text-xs text-muted">Saved metrics based on daily candles.</div>
        <button
          className="h-8 border border-border px-3 text-sm text-primary hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          disabled={isRunning}
          onClick={onRunCheck}
        >
          {isRunning ? "Running..." : "Run Check"}
        </button>
      </div>
      <Tabs active={tab} onChange={setTab} />
      {tab === "Overview" && (
        <>
          <MetricsTable
            signals={currentData.signals}
            dataSource={currentData.data_source}
            fetchedAt={currentData.fetched_at}
            tradingDays={currentData.trading_days}
            promptVersion={currentData.latest_report?.prompt_version}
            modelUsed={currentData.latest_report?.model_used}
          />
          <FundamentalsPanel
            fundamentals={currentData.fundamentals}
            currency={currentData.currency}
            industry={currentData.industry}
          />
          <PriceChart data={currentChartData} />
        </>
      )}
      {tab === "Signals" && <SignalScores signals={currentData.signals} overall={overall} />}
      {tab === "AI Brief" && <AIBrief report={currentData.latest_report} ticker={currentData.ticker} />}
      {tab === "History" && <HistoryTable data={currentChartData} />}
    </div>
  );
}
