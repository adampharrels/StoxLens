from datetime import UTC, datetime, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateTable

from app.api.routes import compare as compare_route
from app.db import models
from app.main import app
from app.services import market_data as market_data_service
from app.services import news as news_service
from app.services import research as research_service
from app.services import triage as triage_service
from app.services.market_data import TickerNotFoundError
from app.services.news import NewsArticle, _article_matches_ticker, classify_news
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


def test_metadata_falls_back_when_alphavantage_overview_is_empty(monkeypatch) -> None:
    market_data_service._metadata_cache.clear()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test")
    monkeypatch.setattr(market_data_service, "_fetch_company_metadata_from_alphavantage", lambda ticker: {})
    monkeypatch.setattr(
        market_data_service,
        "_fetch_company_metadata_from_quote_api",
        lambda ticker: {
            "name": "Microsoft Corporation",
            "exchange": "NasdaqGS",
            "sector": "Equity",
            "industry": "",
            "currency": "USD",
            "market_cap": 3_000_000_000_000,
            "pe_ratio": 34.2,
            "eps": 12.3,
            "revenue_ttm": None,
            "revenue_growth_yoy": None,
            "profit_margin": None,
            "debt_to_equity": None,
            "dividend_yield": 0.007,
        },
    )

    try:
        metadata = market_data_service.fetch_company_metadata("msft")

        assert metadata["name"] == "Microsoft Corporation"
        assert metadata["market_cap"] == 3_000_000_000_000
        assert metadata["pe_ratio"] == 34.2
    finally:
        market_data_service._metadata_cache.clear()


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
    created = client.post(
        "/api/watchlist",
        json={
            "ticker": "nvda",
            "watch_reason": "AI infrastructure demand.",
            "main_risk": "Valuation is expensive.",
            "change_my_mind": "Margins weaken.",
        },
    )
    updated = client.put(
        "/api/watchlist/NVDA",
        json={
            "ticker": "amd",
            "watch_reason": "Data centre GPU share gains.",
            "main_risk": "Execution risk.",
            "change_my_mind": "Demand slows.",
        },
    )
    listed = client.get("/api/watchlist")
    deleted = client.delete("/api/watchlist/AMD")

    assert created.status_code == 201
    assert created.json()["ticker"] == "NVDA"
    assert created.json()["watch_reason"] == "AI infrastructure demand."
    assert updated.status_code == 200
    assert updated.json()["ticker"] == "AMD"
    assert updated.json()["main_risk"] == "Execution risk."
    assert any(item["ticker"] == "AMD" for item in listed.json())
    assert any(item["change_my_mind"] == "Demand slows." for item in listed.json())
    assert deleted.status_code == 204


def test_watchlist_note_columns_have_valid_empty_defaults() -> None:
    ddl = str(CreateTable(models.WatchlistItem.__table__).compile(dialect=sqlite.dialect()))

    assert "watch_reason TEXT DEFAULT '' NOT NULL" in ddl
    assert "main_risk TEXT DEFAULT '' NOT NULL" in ddl
    assert "change_my_mind TEXT DEFAULT '' NOT NULL" in ddl


def test_triage_snapshot_columns_have_defaults_for_existing_databases() -> None:
    ddl = str(CreateTable(models.TriageSnapshot.__table__).compile(dialect=sqlite.dialect()))

    assert "top_news JSON DEFAULT '[]' NOT NULL" in ddl
    assert "price_change_pct FLOAT DEFAULT 0 NOT NULL" in ddl
    assert "as_of_date DATE DEFAULT CURRENT_DATE NOT NULL" in ddl


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
    monkeypatch.setattr(triage_service, "fetch_ticker_news", lambda ticker: [])

    response = client.post("/api/triage/run?tickers=aapl,msft")
    body = response.json()

    assert response.status_code == 200
    assert [item["ticker"] for item in body["items"]] == ["MSFT", "AAPL"]
    assert body["items"][0]["attention_score"] > body["items"][1]["attention_score"]
    assert body["items"][0]["reasons"]
    assert seen == ["AAPL", "MSFT"]


def test_triage_adds_price_relevant_news(monkeypatch) -> None:
    def fake_news(ticker: str) -> list[NewsArticle]:
        return [
            NewsArticle(
                title=f"{ticker} cuts revenue guidance after weak demand",
                url="https://example.com/news",
                source="Example",
                published_at=datetime(2026, 8, 13, 9, 0, tzinfo=UTC),
                summary="",
                category="guidance",
                impact=4,
            )
        ]

    monkeypatch.setattr(triage_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(triage_service, "fetch_ticker_news", fake_news)

    response = client.post("/api/triage/run?tickers=aapl")
    item = response.json()["items"][0]

    assert response.status_code == 200
    assert item["news"][0]["category"] == "guidance"
    assert any(reason["code"] == "news" for reason in item["reasons"])
    assert item["attention_score"] >= 48


def test_get_triage_returns_news_saved_by_run(monkeypatch) -> None:
    def fake_news(ticker: str) -> list[NewsArticle]:
        return [
            NewsArticle(
                title=f"{ticker} raises revenue guidance",
                url="https://example.com/news",
                source="Example",
                published_at=datetime(2026, 8, 13, 9, 0, tzinfo=UTC),
                summary="",
                category="guidance",
                impact=4,
            )
        ]

    triage_service._memory_triage_snapshots.clear()
    monkeypatch.setattr(triage_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(triage_service, "fetch_ticker_news", fake_news)

    try:
        run_response = client.post("/api/triage/run?tickers=aapl")
        read_response = client.get("/api/triage?tickers=aapl")
        read_item = read_response.json()["items"][0]

        assert run_response.status_code == 200
        assert read_response.status_code == 200
        assert read_item["news"][0]["category"] == "guidance"
        assert read_item["news"][0]["title"] == "AAPL raises revenue guidance"
        assert read_item["price_change_pct"] == run_response.json()["items"][0]["price_change_pct"]
        assert read_item["as_of_date"] == run_response.json()["items"][0]["as_of_date"]
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_triage_includes_watch_notes(monkeypatch) -> None:
    monkeypatch.setattr(triage_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(triage_service, "fetch_ticker_news", lambda ticker: [])
    monkeypatch.setattr(
        triage_service,
        "list_watchlist",
        lambda db: [
            {
                "ticker": "MSFT",
                "created_at": datetime(2026, 8, 14, tzinfo=UTC),
                "signal": "Tracked",
                "watch_reason": "Azure growth and AI infrastructure demand.",
                "main_risk": "Valuation is expensive.",
                "change_my_mind": "Cloud growth slows.",
            }
        ],
    )

    response = client.post("/api/triage/run")
    item = response.json()["items"][0]

    assert response.status_code == 200
    assert item["watch_note"]["watch_reason"] == "Azure growth and AI infrastructure demand."
    assert item["watch_note"]["main_risk"] == "Valuation is expensive."


def test_triage_compares_against_previous_snapshot(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_fetch(ticker: str) -> pd.DataFrame:
        calls["count"] += 1
        prices = _prices()
        if calls["count"] > 1:
            prices.iloc[-1, prices.columns.get_loc("Close")] = prices["Close"].iloc[-2] * 0.92
            prices.iloc[-1, prices.columns.get_loc("Adj Close")] = prices["Adj Close"].iloc[-2] * 0.92
            prices.iloc[-1, prices.columns.get_loc("Volume")] = prices["Volume"].iloc[-1] * 3
        return prices

    triage_service._memory_triage_snapshots.clear()
    monkeypatch.setattr(triage_service, "fetch_price_data", fake_fetch)
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(triage_service, "fetch_ticker_news", lambda ticker: [])

    try:
        first = client.post("/api/triage/run?tickers=msft").json()["items"][0]
        second = client.post("/api/triage/run?tickers=msft").json()["items"][0]

        assert first["changes"] is None
        assert second["changes"]["previous_attention_score"] == first["attention_score"]
        assert second["changes"]["score_delta"] == second["attention_score"] - first["attention_score"]
        assert second["changes"]["details"]
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_get_triage_reads_saved_snapshot_without_fetching(monkeypatch) -> None:
    triage_service._memory_triage_snapshots.clear()
    triage_service._memory_triage_snapshots["MSFT"] = [
        {
            "ticker": "MSFT",
            "attention_score": 24,
            "severity": "Low",
            "top_reasons": [{"code": "volume_surge", "label": "Volume surge", "detail": "Volume increased.", "impact": 2}],
            "price": 410.0,
            "price_change_pct": -0.021,
            "as_of_date": "2026-08-14",
            "volume": 1200000.0,
            "rsi": 55.0,
            "moving_average_status": "above_both",
            "created_at": datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
        }
    ]

    def fail_fetch(ticker: str) -> pd.DataFrame:
        raise AssertionError("GET /api/triage must not fetch live market data")

    monkeypatch.setattr(triage_service, "fetch_price_data", fail_fetch)

    try:
        response = client.get("/api/triage?tickers=msft")
        body = response.json()

        assert response.status_code == 200
        assert body["items"][0]["ticker"] == "MSFT"
        assert body["items"][0]["attention_score"] == 24
        assert body["items"][0]["price_change_pct"] == -0.021
        assert body["items"][0]["as_of_date"] == "2026-08-14"
        assert body["items"][0]["reasons"][0]["code"] == "volume_surge"
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_news_classifier_ignores_generic_articles() -> None:
    assert classify_news("Company announces quarterly earnings date") == ("earnings", 4)
    assert classify_news("Company mentioned in generic market wrap") == ("general", 0)
    assert classify_news("Bank platform response improves in seconds") == ("general", 0)
    assert classify_news("Software vendor expands banking tools") == ("general", 0)


def test_news_classifier_matches_whole_keywords_and_phrases() -> None:
    assert classify_news("SEC opens investigation into disclosure practices") == ("regulatory", 4)
    assert classify_news("Company faces export ban in key market") == ("regulatory", 4)
    assert classify_news("Board reviews M&A options") == ("m&a", 3)
    assert classify_news("Company cuts forecast after weak demand") == ("guidance", 4)


def test_news_filter_requires_ticker_relevance() -> None:
    assert _article_matches_ticker({"ticker_sentiment": [{"ticker": "NVDA"}], "title": "Chip news"}, "NVDA")
    assert _article_matches_ticker({"ticker_sentiment": [], "title": "Nvidia partners with $NVDA supplier"}, "NVDA")
    assert not _article_matches_ticker({"ticker_sentiment": [{"ticker": "IBM"}], "title": "IBM fund filing"}, "NVDA")


def test_news_endpoint_returns_classified_articles(monkeypatch) -> None:
    def fake_news(ticker: str, *, limit: int = 5, lookback=None) -> list[NewsArticle]:
        return [
            NewsArticle(
                title=f"{ticker} receives analyst upgrade",
                url="https://example.com/upgrade",
                source="Example",
                published_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
                summary="",
                category="analyst",
                impact=2,
            )
        ][:limit]

    monkeypatch.setattr("app.api.routes.news.fetch_ticker_news", fake_news)

    response = client.get("/api/news/aapl?limit=1&lookback_hours=48")

    assert response.status_code == 200
    assert response.json()[0]["category"] == "analyst"
    assert response.json()[0]["impact"] == 2


def test_news_cache_prunes_expired_lookback_entries(monkeypatch) -> None:
    news_service._news_cache.clear()
    news_service._news_cache["AAPL:3600"] = (datetime(2000, 1, 1, tzinfo=UTC), [])
    monkeypatch.setattr(news_service, "_fetch_alphavantage_news", lambda ticker, *, lookback: [])

    try:
        news_service.fetch_ticker_news("msft", lookback=timedelta(hours=2))

        assert "AAPL:3600" not in news_service._news_cache
        assert "MSFT:7200" in news_service._news_cache
    finally:
        news_service._news_cache.clear()
