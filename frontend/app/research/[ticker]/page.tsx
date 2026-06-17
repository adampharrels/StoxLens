import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { ResearchWorkspace } from "@/components/research/ResearchWorkspace";
import { getResearch } from "@/lib/api";

export default async function ResearchPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  try {
    const data = await getResearch(ticker);
    return <ResearchWorkspace data={data} />;
  } catch {
    return <ApiUnavailable title={`Research · ${ticker.toUpperCase()}`} />;
  }
}
