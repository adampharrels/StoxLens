from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.research import FundamentalsOut, PricePoint, ResearchResponse, SignalSnapshotOut
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
)
from app.services.reports import latest_report, report_to_schema, save_report
from app.services.signals import calculate_signals


def load_clean_prices(ticker: str):
    try:
        return clean_price_data(fetch_price_data(ticker))
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientPriceDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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


def _build_response(ticker: str, df, signals: dict, report, meta: dict[str, Any]) -> ResearchResponse:
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
        data_source=market_data_source(),
        fetched_at=datetime.utcnow(),
        trading_days=len(df),
        prompt_version=PROMPT_VERSION,
        model_used=MODEL_USED,
        signals=SignalSnapshotOut.model_validate(signals),
        latest_report=report_to_schema(report) if report else None,
        price_history=_history(df),
    )


def get_research_snapshot(ticker: str, db: Session | None) -> ResearchResponse:
    df = load_clean_prices(ticker)
    signals = _signals_with_quality(df)
    report = latest_report(db, ticker)
    return _build_response(ticker, df, signals, report, fetch_company_metadata(ticker))


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
    return _build_response(ticker, df, signals, report, fetch_company_metadata(ticker))
