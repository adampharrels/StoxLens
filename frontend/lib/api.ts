import type { ReportListItem, ResearchResponse, SignalSnapshot } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API request failed: ${res.status}`);
  }
  return res.json();
}

async function postJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API request failed: ${res.status}`);
  }
  return res.json();
}

export const getResearch = (ticker: string) => getJson<ResearchResponse>(`/api/research/${encodeURIComponent(ticker)}`);

export const generateResearch = (ticker: string) =>
  postJson<ResearchResponse>(`/api/research/${encodeURIComponent(ticker)}/generate`);

export const getReports = () => getJson<ReportListItem[]>("/api/reports");

export const getCompare = (tickers: string[] = ["AAPL", "MSFT", "IBM"]) => {
  const query = new URLSearchParams({ tickers: tickers.join(",") });
  return getJson<Record<string, SignalSnapshot>>(`/api/compare?${query.toString()}`);
};

export const getWatchlist = () => getJson<{ ticker: string; signal: string; created_at: string }[]>("/api/watchlist");
