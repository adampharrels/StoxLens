import type { ReportListItem, ResearchResponse, SignalSnapshot } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

async function postJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return res.json();
}

export const getResearch = (ticker: string) => getJson<ResearchResponse>(`/api/research/${encodeURIComponent(ticker)}`);

export const generateResearch = (ticker: string) =>
  postJson<ResearchResponse>(`/api/research/${encodeURIComponent(ticker)}/generate`);

export const getReports = () => getJson<ReportListItem[]>("/api/reports");

export const getCompare = () => getJson<Record<string, SignalSnapshot>>("/api/compare");

export const getWatchlist = () => getJson<{ ticker: string; signal: string }[]>("/api/watchlist");
