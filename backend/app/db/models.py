from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


JsonType = JSON().with_variant(JSONB, "postgresql")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    exchange: Mapped[str] = mapped_column(String(40), default="")
    sector: Mapped[str] = mapped_column(String(80), default="")
    industry: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    date: Mapped[datetime] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    adj_close: Mapped[float] = mapped_column(Float)


class SignalSnapshot(Base):
    __tablename__ = "signal_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    as_of_date: Mapped[datetime] = mapped_column(Date)
    return_1m: Mapped[float] = mapped_column(Float)
    return_3m: Mapped[float] = mapped_column(Float)
    return_6m: Mapped[float] = mapped_column(Float)
    return_12m: Mapped[float] = mapped_column(Float)
    volatility_30d: Mapped[float] = mapped_column(Float)
    volatility_90d: Mapped[float] = mapped_column(Float)
    max_drawdown: Mapped[float] = mapped_column(Float)
    ma_signal: Mapped[str] = mapped_column(String(24))
    rsi: Mapped[float] = mapped_column(Float)
    volume_trend: Mapped[float] = mapped_column(Float)
    momentum_score: Mapped[int] = mapped_column(Integer)
    trend_score: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)
    data_quality_score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reports: Mapped[list["ResearchReport"]] = relationship(back_populates="signal_snapshot")


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    signal_snapshot_id: Mapped[int] = mapped_column(ForeignKey("signal_snapshots.id"))
    summary: Mapped[str] = mapped_column(Text)
    positive_signals: Mapped[list[str]] = mapped_column(JsonType)
    negative_signals: Mapped[list[str]] = mapped_column(JsonType)
    risks: Mapped[list[str]] = mapped_column(JsonType)
    data_quality_notes: Mapped[list[str]] = mapped_column(JsonType)
    questions_for_research: Mapped[list[str]] = mapped_column(JsonType)
    overall_view: Mapped[str] = mapped_column(String(24))
    model_used: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    signal_snapshot: Mapped[SignalSnapshot] = relationship(back_populates="reports")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    watch_reason: Mapped[str] = mapped_column(Text, default="", server_default=text("''"), nullable=False)
    main_risk: Mapped[str] = mapped_column(Text, default="", server_default=text("''"), nullable=False)
    change_my_mind: Mapped[str] = mapped_column(Text, default="", server_default=text("''"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TriageSnapshot(Base):
    __tablename__ = "triage_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    attention_score: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(12))
    top_reasons: Mapped[list[dict[str, str | int]]] = mapped_column(JsonType)
    top_news: Mapped[list[dict[str, str | int]]] = mapped_column(JsonType, default=list, server_default=text("'[]'"), nullable=False)
    price: Mapped[float] = mapped_column(Float)
    price_change_pct: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, default=date.today, server_default=text("CURRENT_DATE"), nullable=False)
    volume: Mapped[float] = mapped_column(Float)
    rsi: Mapped[float] = mapped_column(Float)
    moving_average_status: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
