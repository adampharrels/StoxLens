import { CompareTable } from "@/components/compare/CompareTable";
import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { ApiError, getCompare } from "@/lib/api";
import { Search } from "lucide-react";

function parseTickers(value?: string) {
  const parsed = (value ?? "AAPL, MSFT, IBM")
    .split(",")
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 8);
  return parsed.length > 0 ? parsed : ["AAPL", "MSFT", "IBM"];
}

export default async function ComparePage({ searchParams }: { searchParams?: Promise<{ tickers?: string }> }) {
  const params = await searchParams;
  const tickers = parseTickers(params?.tickers);
  try {
    const data = await getCompare(tickers);
    return (
      <div className="px-6 py-4">
        <div className="mb-4 text-lg font-medium">Compare</div>
        <form action="/compare" className="mb-5 flex max-w-[560px] gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              name="tickers"
              aria-label="Tickers to compare"
              defaultValue={tickers.join(", ")}
              className="h-8 w-full rounded-none border border-border bg-surface pl-8 pr-2 text-base text-primary"
            />
          </div>
          <button type="submit" className="h-8 border border-accent bg-accent px-3 text-sm text-white">
            Compare
          </button>
        </form>
        <CompareTable data={data} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable title="Compare" message={error.message} />;
    }
    return <ApiUnavailable title="Compare" />;
  }
}
