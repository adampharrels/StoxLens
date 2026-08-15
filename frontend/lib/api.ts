import type { ReportListItem, ResearchResponse, SignalSnapshot, TriageResponse, WatchlistItem } from "@/lib/types";

export interface WatchlistPayload {
  ticker: string;
  watch_reason?: string;
  main_risk?: string;
  change_my_mind?: string;
}

const BROWSER_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SERVER_API_URL = process.env.SERVER_API_URL ?? BROWSER_API_URL;

const apiUrl = () => (typeof window === "undefined" ? SERVER_API_URL : BROWSER_API_URL);

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${apiUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API request failed: ${res.status}`);
  }
  return res.json();
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${apiUrl()}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API request failed: ${res.status}`);
  }
  return res.json();
}

async function putJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${apiUrl()}${path}`, {
    method: "PUT",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API request failed: ${res.status}`);
  }
  return res.json();
}

async function deleteJson(path: string): Promise<void> {
  const res = await fetch(`${apiUrl()}${path}`, { method: "DELETE", cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API request failed: ${res.status}`);
  }
}

export const getResearch = (ticker: string) => getJson<ResearchResponse>(`/api/research/${encodeURIComponent(ticker)}`);

export const generateResearch = (ticker: string) =>
  postJson<ResearchResponse>(`/api/research/${encodeURIComponent(ticker)}/generate`);

export const getReports = () => getJson<ReportListItem[]>("/api/reports");

export const getCompare = (tickers: string[] = ["AAPL", "MSFT", "IBM"]) => {
  const query = new URLSearchParams({ tickers: tickers.join(",") });
  return getJson<Record<string, SignalSnapshot>>(`/api/compare?${query.toString()}`);
};

export const getWatchlist = () => getJson<WatchlistItem[]>("/api/watchlist");

export const addWatchlistItem = (payload: WatchlistPayload) => postJson<WatchlistItem>("/api/watchlist", payload);

export const updateWatchlistItem = (ticker: string, payload: WatchlistPayload) =>
  putJson<WatchlistItem>(`/api/watchlist/${encodeURIComponent(ticker)}`, payload);

export const removeWatchlistItem = (ticker: string) => deleteJson(`/api/watchlist/${encodeURIComponent(ticker)}`);

export const getTriage = () => getJson<TriageResponse>("/api/triage");
