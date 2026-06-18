export interface SignalSnapshot {
  return_1m: number;
  return_3m: number;
  return_6m: number;
  return_12m: number;
  volatility_30d: number;
  volatility_90d: number;
  max_drawdown: number;
  ma_signal: "above_both" | "above_50_only" | "below_both";
  rsi: number;
  volume_trend: number;
  momentum_score: number;
  trend_score: number;
  risk_score: number;
  data_quality_score: number;
  as_of_date: string;
}

export interface ResearchReport {
  id: string;
  ticker: string;
  summary: string;
  positive_signals: string[];
  negative_signals: string[];
  risks: string[];
  data_quality_notes: string[];
  questions_for_research: string[];
  overall_view: "Watchlist" | "Needs Review" | "Weak Signal";
  model_used: string;
  prompt_version: string;
  created_at: string;
  signal_snapshot: SignalSnapshot;
}

export interface PricePoint {
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close: number;
  volume?: number;
  adj_close?: number;
}

export interface ResearchResponse {
  ticker: string;
  company_name: string;
  exchange: string;
  sector: string;
  price: number;
  price_change_pct: number;
  data_source?: string;
  fetched_at?: string;
  trading_days?: number;
  prompt_version?: string;
  model_used?: string;
  signals: SignalSnapshot;
  latest_report: ResearchReport | null;
  price_history: PricePoint[];
}

export interface ReportListItem {
  id: string;
  ticker: string;
  created_at: string;
  summary: string;
  overall_view: string;
}
