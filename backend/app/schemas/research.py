from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SignalSnapshotOut(BaseModel):
    return_1m: float
    return_3m: float
    return_6m: float
    return_12m: float
    volatility_30d: float
    volatility_90d: float
    max_drawdown: float
    ma_signal: Literal["above_both", "above_50_only", "below_both"]
    rsi: float
    volume_trend: float
    momentum_score: int = Field(ge=0, le=5)
    trend_score: int = Field(ge=0, le=5)
    risk_score: int = Field(ge=0, le=5)
    data_quality_score: int = Field(ge=0, le=5)
    as_of_date: date


class BriefPayload(BaseModel):
    summary: str
    positive_signals: list[str]
    negative_signals: list[str]
    risks: list[str]
    data_quality_notes: list[str]
    questions_for_research: list[str]
    overall_view: Literal["Watchlist", "Needs Review", "Weak Signal"]


class ResearchReportOut(BriefPayload):
    id: str
    ticker: str
    model_used: str
    prompt_version: str
    created_at: datetime
    signal_snapshot: SignalSnapshotOut


class PricePoint(BaseModel):
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None
    adj_close: float | None = None


class FundamentalsOut(BaseModel):
    market_cap: int | None = None
    pe_ratio: float | None = None
    eps: float | None = None
    revenue_ttm: int | None = None
    revenue_growth_yoy: float | None = None
    profit_margin: float | None = None
    debt_to_equity: float | None = None
    dividend_yield: float | None = None


class ResearchResponse(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    sector: str
    industry: str
    currency: str
    price: float
    price_change_pct: float
    fundamentals: FundamentalsOut
    data_source: str
    fetched_at: datetime
    trading_days: int
    prompt_version: str
    model_used: str
    signals: SignalSnapshotOut
    latest_report: ResearchReportOut | None
    price_history: list[PricePoint]


class NoSnapshotResponse(BaseModel):
    ticker: str
    status: Literal["no_snapshot"]
    message: str
