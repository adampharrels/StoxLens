from datetime import datetime

import pandas as pd
from fastapi.testclient import TestClient

from app.api.routes import compare as compare_route
from app.main import app
from app.services import research as research_service
from app.services import triage as triage_service
from app.services.market_data import TickerNotFoundError
from app.services.rate_limit import clear_rate_limits

client = TestClient(app)


def _prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=280, freq="B")
    close = [float(100 + index) for index in range(len(dates))]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [price + 1 for price in close],
            "Low": [price - 1 for price in close],
            "Close": close,
            "Volume": [1_000_000 + index for index in range(len(dates))],
            "Adj Close": close,
        },
        index=dates,
    )


def test_compare_uses_caller_supplied_tickers(monkeypatch) -> None:
    seen: list[str] = []

    def fake_fetch(ticker: str) -> pd.DataFrame:
        seen.append(ticker)
        return _prices()

    monkeypatch.setattr(compare_route, "fetch_price_data", fake_fetch)
    monkeypatch.setattr(compare_route, "clean_price_data", lambda df: df)

    response = client.get("/api/compare?tickers=msft,nvda")

    assert response.status_code == 200
    assert list(response.json()) == ["MSFT", "NVDA"]
    assert seen == ["MSFT", "NVDA"]


def test_compare_requires_at_least_one_ticker() -> None:
    response = client.get("/api/compare?tickers=,,,")

    assert response.status_code == 422
    assert response.json()["detail"] == "At least one ticker is required."


def test_research_maps_missing_ticker_to_404(monkeypatch) -> None:
    def fake_fetch(ticker: str) -> pd.DataFrame:
        raise TickerNotFoundError(f"No market data found for {ticker}")

    monkeypatch.setattr(research_service, "fetch_price_data", fake_fetch)

    response = client.get("/api/research/MISSING")

    assert response.status_code == 404
    assert "MISSING" in response.json()["detail"]


def test_generate_research_is_rate_limited(monkeypatch) -> None:
    clear_rate_limits()
    monkeypatch.setenv("RESEARCH_GENERATE_LIMIT", "1")
    monkeypatch.setenv("RESEARCH_GENERATE_WINDOW_SECONDS", "60")

    def fake_snapshot(ticker: str, db) -> dict:
        return {
            "ticker": ticker,
            "company_name": ticker,
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Software",
            "currency": "USD",
            "price": 101.0,
            "price_change_pct": 0.01,
            "fundamentals": {},
            "data_source": "test",
            "fetched_at": datetime.utcnow().isoformat(),
            "trading_days": 280,
            "prompt_version": "test",
            "model_used": "test",
            "signals": {
                "return_1m": 0.01,
                "return_3m": 0.02,
                "return_6m": 0.03,
                "return_12m": 0.04,
                "volatility_30d": 0.1,
                "volatility_90d": 0.1,
                "max_drawdown": -0.05,
                "ma_signal": "above_both",
                "rsi": 55,
                "volume_trend": 0.02,
                "momentum_score": 4,
                "trend_score": 4,
                "risk_score": 4,
                "data_quality_score": 5,
                "as_of_date": "2024-12-31",
            },
            "latest_report": None,
            "price_history": [],
        }

    monkeypatch.setattr("app.api.routes.research.generate_research_snapshot", fake_snapshot)

    first = client.post("/api/research/AAPL/generate")
    second = client.post("/api/research/AAPL/generate")

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    clear_rate_limits()


def test_watchlist_can_add_and_remove_items() -> None:
    created = client.post("/api/watchlist", json={"ticker": "nvda"})
    listed = client.get("/api/watchlist")
    deleted = client.delete("/api/watchlist/NVDA")

    assert created.status_code == 201
    assert created.json()["ticker"] == "NVDA"
    assert any(item["ticker"] == "NVDA" for item in listed.json())
    assert deleted.status_code == 204


def test_triage_ranks_watchlist_attention(monkeypatch) -> None:
    seen: list[str] = []

    def fake_fetch(ticker: str) -> pd.DataFrame:
        seen.append(ticker)
        prices = _prices()
        if ticker == "MSFT":
            prices.iloc[-1, prices.columns.get_loc("Close")] = prices["Close"].iloc[-2] * 0.92
            prices.iloc[-1, prices.columns.get_loc("Adj Close")] = prices["Adj Close"].iloc[-2] * 0.92
            prices.iloc[-1, prices.columns.get_loc("Volume")] = prices["Volume"].iloc[-1] * 3
        return prices

    monkeypatch.setattr(triage_service, "fetch_price_data", fake_fetch)
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)

    response = client.get("/api/triage?tickers=aapl,msft")
    body = response.json()

    assert response.status_code == 200
    assert [item["ticker"] for item in body["items"]] == ["MSFT", "AAPL"]
    assert body["items"][0]["attention_score"] > body["items"][1]["attention_score"]
    assert body["items"][0]["reasons"]
    assert seen == ["AAPL", "MSFT"]
