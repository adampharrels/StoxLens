from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException
import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.research import FundamentalsOut, NoSnapshotResponse, PricePoint, ResearchResponse, SignalSnapshotOut
from app.services.llm import MODEL_USED, PROMPT_VERSION, build_prompt, call_llm, parse_and_validate_brief
from app.services.market_data import (
    InsufficientPriceDataError,
    MarketDataError,
    RateLimitError,
    TickerNotFoundError,
    assess_data_quality,
    clean_price_data,
    fetch_company_metadata,
    fetch_price_data,
    market_data_source,
    public_market_data_error,
)
from app.services.reports import latest_report, report_to_schema, save_report
from app.services.signals import calculate_signals

_memory_research_snapshots: dict[str, dict[str, Any]] = {}
_FUNDAMENTAL_FIELDS = (
    "market_cap",
    "pe_ratio",
    "eps",
    "revenue_ttm",
    "revenue_growth_yoy",
    "profit_margin",
    "debt_to_equity",
    "dividend_yield",
)
_COMPANY_CONTEXT_FIELDS = ("exchange", "industry", "currency")


def load_clean_prices(ticker: str):
    try:
        return clean_price_data(fetch_price_data(ticker))
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientPriceDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=public_market_data_error(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=public_market_data_error(exc)) from exc


def _history(df) -> list[PricePoint]:
    rows = df.tail(252)
    return [
        PricePoint(
            date=index.date(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
            adj_close=float(row["Adj Close"]),
        )
        for index, row in rows.iterrows()
    ]


def _signals_with_quality(df) -> dict[str, Any]:
    signals = calculate_signals(df)
    quality = assess_data_quality(df)
    signals["data_quality_score"] = int(quality["score"])
    return signals


def _empty_metadata(ticker: str) -> dict[str, Any]:
    return {
        "name": ticker.upper(),
        "exchange": "",
        "sector": "Equity",
        "industry": "",
        "currency": "",
        "market_cap": None,
        "pe_ratio": None,
        "eps": None,
        "revenue_ttm": None,
        "revenue_growth_yoy": None,
        "profit_margin": None,
        "debt_to_equity": None,
        "dividend_yield": None,
    }


def _has_useful_metadata(meta: dict[str, Any]) -> bool:
    has_fundamentals = any(meta.get(field) is not None for field in _FUNDAMENTAL_FIELDS)
    has_context = any(bool(meta.get(field)) for field in _COMPANY_CONTEXT_FIELDS)
    return has_fundamentals or has_context


def _merge_saved_metadata(saved: dict[str, Any], fresh: dict[str, Any], ticker: str) -> dict[str, Any]:
    merged = fresh.copy()
    for field in (*_COMPANY_CONTEXT_FIELDS, *_FUNDAMENTAL_FIELDS):
        if merged.get(field) in (None, "") and saved.get(field) not in (None, ""):
            merged[field] = saved[field]
    if merged.get("sector") in (None, "", "Equity") and saved.get("sector") not in (None, "", "Equity"):
        merged["sector"] = saved["sector"]
    fresh_name = str(merged.get("name") or "").strip()
    saved_name = str(saved.get("name") or "").strip()
    if saved_name and (not fresh_name or fresh_name.upper() == ticker.upper()):
        merged["name"] = saved["name"]
    return merged


def _build_response(
    ticker: str,
    df,
    signals: dict,
    report,
    meta: dict[str, Any],
    *,
    data_source: str,
    fetched_at: datetime,
) -> ResearchResponse:
    close = df["Close"]
    price_change_pct = float((close.iloc[-1] / close.iloc[-2]) - 1) if len(close) > 1 else 0
    return ResearchResponse(
        ticker=ticker.upper(),
        company_name=meta["name"],
        exchange=meta["exchange"],
        sector=meta["sector"],
        industry=meta["industry"],
        currency=meta["currency"],
        price=float(close.iloc[-1]),
        price_change_pct=price_change_pct,
        fundamentals=FundamentalsOut(
            market_cap=meta.get("market_cap"),
            pe_ratio=meta.get("pe_ratio"),
            eps=meta.get("eps"),
            revenue_ttm=meta.get("revenue_ttm"),
            revenue_growth_yoy=meta.get("revenue_growth_yoy"),
            profit_margin=meta.get("profit_margin"),
            debt_to_equity=meta.get("debt_to_equity"),
            dividend_yield=meta.get("dividend_yield"),
        ),
        data_source=data_source,
        fetched_at=fetched_at,
        trading_days=len(df),
        prompt_version=PROMPT_VERSION,
        model_used=MODEL_USED,
        signals=SignalSnapshotOut.model_validate(signals),
        latest_report=report_to_schema(report) if report else None,
        price_history=_history(df),
    )


def _signal_payload(snapshot: models.SignalSnapshot) -> dict[str, Any]:
    return {
        "return_1m": snapshot.return_1m,
        "return_3m": snapshot.return_3m,
        "return_6m": snapshot.return_6m,
        "return_12m": snapshot.return_12m,
        "volatility_30d": snapshot.volatility_30d,
        "volatility_90d": snapshot.volatility_90d,
        "max_drawdown": snapshot.max_drawdown,
        "ma_signal": snapshot.ma_signal,
        "rsi": snapshot.rsi,
        "volume_trend": snapshot.volume_trend,
        "momentum_score": snapshot.momentum_score,
        "trend_score": snapshot.trend_score,
        "risk_score": snapshot.risk_score,
        "data_quality_score": snapshot.data_quality_score,
        "as_of_date": snapshot.as_of_date,
    }


def _save_company(db: Session, ticker: str, meta: dict[str, Any]) -> None:
    company = db.query(models.Company).filter(models.Company.ticker == ticker.upper()).first()
    if company is None:
        company = models.Company(ticker=ticker.upper(), name=meta["name"])
        db.add(company)
    company.name = meta["name"]
    company.exchange = meta["exchange"]
    company.sector = meta["sector"]
    company.industry = meta["industry"]
    company.currency = meta["currency"]
    company.market_cap = meta.get("market_cap")
    company.pe_ratio = meta.get("pe_ratio")
    company.eps = meta.get("eps")
    company.revenue_ttm = meta.get("revenue_ttm")
    company.revenue_growth_yoy = meta.get("revenue_growth_yoy")
    company.profit_margin = meta.get("profit_margin")
    company.debt_to_equity = meta.get("debt_to_equity")
    company.dividend_yield = meta.get("dividend_yield")


def _company_metadata(db: Session | None, ticker: str) -> dict[str, Any]:
    key = ticker.upper()
    if db is None:
        cached = _memory_research_snapshots.get(key)
        return cached["meta"].copy() if cached else _empty_metadata(key)

    company = db.query(models.Company).filter(models.Company.ticker == key).first()
    if company is None:
        return _empty_metadata(key)
    return {
        **_empty_metadata(key),
        "name": company.name,
        "exchange": company.exchange,
        "sector": company.sector,
        "industry": company.industry,
        "currency": company.currency,
        "market_cap": company.market_cap,
        "pe_ratio": company.pe_ratio,
        "eps": company.eps,
        "revenue_ttm": company.revenue_ttm,
        "revenue_growth_yoy": company.revenue_growth_yoy,
        "profit_margin": company.profit_margin,
        "debt_to_equity": company.debt_to_equity,
        "dividend_yield": company.dividend_yield,
    }


def _save_price_history(db: Session, ticker: str, df) -> None:
    key = ticker.upper()
    # Store the same daily candle window the research page can render without refetching providers.
    rows = df.tail(252)
    dates = [index.date() for index in rows.index]
    db.query(models.PriceHistory).filter(models.PriceHistory.ticker == key, models.PriceHistory.date.in_(dates)).delete(
        synchronize_session=False
    )
    for index, row in rows.iterrows():
        db.add(
            models.PriceHistory(
                ticker=key,
                date=index.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                adj_close=float(row["Adj Close"]),
            )
        )


def saved_price_history(db: Session | None, ticker: str):
    key = ticker.upper()
    if db is None:
        cached = _memory_research_snapshots.get(key)
        return cached["df"].copy() if cached else None

    rows = (
        db.query(models.PriceHistory)
        .filter(models.PriceHistory.ticker == key)
        .order_by(desc(models.PriceHistory.date))
        .limit(252)
        .all()
    )
    if not rows:
        return None
    rows = list(reversed(rows))
    return pd.DataFrame(
        {
            "Open": [row.open for row in rows],
            "High": [row.high for row in rows],
            "Low": [row.low for row in rows],
            "Close": [row.close for row in rows],
            "Volume": [row.volume for row in rows],
            "Adj Close": [row.adj_close for row in rows],
        },
        index=pd.to_datetime([row.date for row in rows]),
    )


def _save_signal_snapshot(db: Session, ticker: str, signals: dict[str, Any]) -> models.SignalSnapshot:
    snapshot = models.SignalSnapshot(
        ticker=ticker.upper(),
        as_of_date=date.fromisoformat(str(signals["as_of_date"])),
        return_1m=signals["return_1m"],
        return_3m=signals["return_3m"],
        return_6m=signals["return_6m"],
        return_12m=signals["return_12m"],
        volatility_30d=signals["volatility_30d"],
        volatility_90d=signals["volatility_90d"],
        max_drawdown=signals["max_drawdown"],
        ma_signal=signals["ma_signal"],
        rsi=signals["rsi"],
        volume_trend=signals["volume_trend"],
        momentum_score=signals["momentum_score"],
        trend_score=signals["trend_score"],
        risk_score=signals["risk_score"],
        data_quality_score=signals["data_quality_score"],
    )
    db.add(snapshot)
    return snapshot


def _latest_signal_snapshot(db: Session | None, ticker: str) -> tuple[dict[str, Any], datetime] | None:
    key = ticker.upper()
    if db is None:
        cached = _memory_research_snapshots.get(key)
        if not cached:
            return None
        return cached["signals"].copy(), cached["fetched_at"]

    snapshot = (
        db.query(models.SignalSnapshot)
        .filter(models.SignalSnapshot.ticker == key)
        .order_by(desc(models.SignalSnapshot.created_at), desc(models.SignalSnapshot.id))
        .first()
    )
    return (_signal_payload(snapshot), snapshot.created_at) if snapshot else None


def _no_snapshot(ticker: str) -> NoSnapshotResponse:
    return NoSnapshotResponse(ticker=ticker.upper(), status="no_snapshot", message="No full check has been run yet.")


def get_research_snapshot(ticker: str, db: Session | None) -> ResearchResponse | NoSnapshotResponse:
    # GET is intentionally read-only, so users can open/search tickers without spending API quota.
    saved_signal = _latest_signal_snapshot(db, ticker)
    df = saved_price_history(db, ticker)
    if saved_signal is None or df is None:
        return _no_snapshot(ticker)

    signals, fetched_at = saved_signal
    report = latest_report(db, ticker)
    return _build_response(
        ticker,
        df,
        signals,
        report,
        _company_metadata(db, ticker),
        data_source="saved",
        fetched_at=fetched_at,
    )


def run_research_check(ticker: str, db: Session | None) -> ResearchResponse:
    # This is the explicit refresh path behind the Run Check button.
    df = load_clean_prices(ticker)
    signals = _signals_with_quality(df)
    meta = fetch_company_metadata(ticker)
    fetched_at = datetime.now(UTC)
    if db is None:
        cached = _memory_research_snapshots.get(ticker.upper())
        if cached:
            meta = _merge_saved_metadata(cached["meta"], meta, ticker)
        _memory_research_snapshots[ticker.upper()] = {
            "df": df.copy(),
            "signals": signals.copy(),
            "meta": meta.copy(),
            "fetched_at": fetched_at,
        }
    else:
        saved_meta = _company_metadata(db, ticker)
        meta = _merge_saved_metadata(saved_meta, meta, ticker)
        _save_company(db, ticker, meta)
        _save_price_history(db, ticker, df)
        _save_signal_snapshot(db, ticker, signals)
        db.commit()
    report = latest_report(db, ticker)
    return _build_response(ticker, df, signals, report, meta, data_source=market_data_source(), fetched_at=fetched_at)


def generate_research_snapshot(ticker: str, db: Session | None) -> ResearchResponse:
    df = load_clean_prices(ticker)
    signals = _signals_with_quality(df)
    quality = assess_data_quality(df)
    prompt = build_prompt(ticker.upper(), signals, quality)
    response = call_llm(prompt)
    brief = parse_and_validate_brief(response, ticker.upper(), signals, quality)
    report = save_report(
        db,
        ticker,
        signals,
        brief,
        {"model_used": MODEL_USED, "prompt_version": PROMPT_VERSION},
    )
    meta = fetch_company_metadata(ticker)
    if db is None:
        cached = _memory_research_snapshots.get(ticker.upper())
        if cached:
            meta = _merge_saved_metadata(cached["meta"], meta, ticker)
        _memory_research_snapshots[ticker.upper()] = {
            "df": df.copy(),
            "signals": signals.copy(),
            "meta": meta.copy(),
            "fetched_at": datetime.now(UTC),
        }
    else:
        saved_meta = _company_metadata(db, ticker)
        meta = _merge_saved_metadata(saved_meta, meta, ticker)
        _save_company(db, ticker, meta)
        _save_price_history(db, ticker, df)
        db.commit()
    return _build_response(ticker, df, signals, report, meta, data_source=market_data_source(), fetched_at=datetime.now(UTC))
