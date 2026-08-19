import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { ResearchWorkspace } from "@/components/research/ResearchWorkspace";
import { ApiError, getChart, getResearch, runResearch } from "@/lib/api";
import type { NoSnapshotResponse, ResearchResult } from "@/lib/types";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

function isNoSnapshot(data: ResearchResult): data is NoSnapshotResponse {
  return "status" in data && data.status === "no_snapshot";
}

async function runResearchAction(formData: FormData) {
  "use server";
  const ticker = String(formData.get("ticker") || "").toUpperCase();
  if (!ticker) return;
  await runResearch(ticker);
  revalidatePath(`/research/${ticker}`);
  redirect(`/research/${ticker}`);
}

export default async function ResearchPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  try {
    // Research metrics and chart candles are separate reads so charting can stay saved-data only.
    const [data, chartData] = await Promise.all([getResearch(ticker), getChart(ticker)]);
    if (isNoSnapshot(data)) {
      return (
        <div className="px-6 py-8">
          <div className="text-lg font-medium">{data.ticker}</div>
          <div className="mt-2 max-w-[520px] text-sm leading-6 text-secondary">{data.message}</div>
          <form action={runResearchAction} className="mt-4">
            <input type="hidden" name="ticker" value={data.ticker} />
            <button className="h-8 border border-border px-3 text-sm text-primary hover:border-accent" type="submit">
              Run Check
            </button>
          </form>
        </div>
      );
    }
    return <ResearchWorkspace data={data} chartData={chartData} />;
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable title={`Research · ${ticker.toUpperCase()}`} message={error.message} />;
    }
    return <ApiUnavailable title={`Research · ${ticker.toUpperCase()}`} />;
  }
}
