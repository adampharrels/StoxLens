from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import PricePoint, ResearchResponse, SignalSnapshotOut
from app.services.llm import MODEL_USED, PROMPT_VERSION, build_prompt, call_llm, parse_and_validate_brief
from app.services.market_data import assess_data_quality, clean_price_data, fetch_price_data
from app.services.reports import latest_report, report_to_schema, save_report
from app.services.signals import calculate_signals

router = APIRouter()

COMPANY_META = {
    "BHP.AX": {"name": "BHP Group", "exchange": "ASX", "sector": "Materials"},
    "CBA.AX": {"name": "Commonwealth Bank", "exchange": "ASX", "sector": "Financials"},
    "RIO.AX": {"name": "Rio Tinto", "exchange": "ASX", "sector": "Materials"},
    "AAPL": {"name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Technology"},
}


def _company_meta(ticker: str) -> dict[str, str]:
    return COMPANY_META.get(ticker.upper(), {"name": ticker.upper(), "exchange": "", "sector": "Equity"})


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


def _build_response(ticker: str, df, signals: dict, report) -> ResearchResponse:
    meta = _company_meta(ticker)
    close = df["Close"]
    price_change_pct = float((close.iloc[-1] / close.iloc[-2]) - 1) if len(close) > 1 else 0
    return ResearchResponse(
        ticker=ticker.upper(),
        company_name=meta["name"],
        exchange=meta["exchange"],
        sector=meta["sector"],
        price=float(close.iloc[-1]),
        price_change_pct=price_change_pct,
        signals=SignalSnapshotOut.model_validate(signals),
        latest_report=report_to_schema(report) if report else None,
        price_history=_history(df),
    )


@router.post("/{ticker}/generate", response_model=ResearchResponse)
def generate_research(ticker: str, db: Session | None = Depends(get_db)) -> ResearchResponse:
    df = fetch_price_data(ticker)
    df = clean_price_data(df)
    signals = calculate_signals(df)
    quality = assess_data_quality(df)
    signals["data_quality_score"] = int(quality["score"])
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
    return _build_response(ticker, df, signals, report)


@router.get("/{ticker}", response_model=ResearchResponse)
def get_research(ticker: str, db: Session | None = Depends(get_db)) -> ResearchResponse:
    df = clean_price_data(fetch_price_data(ticker))
    signals = calculate_signals(df)
    quality = assess_data_quality(df)
    signals["data_quality_score"] = int(quality["score"])
    report = latest_report(db, ticker)
    return _build_response(ticker, df, signals, report)
