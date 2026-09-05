from datetime import UTC, datetime, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateTable
from starlette.websockets import WebSocketDisconnect

from app.api.routes import compare as compare_route
from app.api.routes import candles as candles_route
from app.db import models
from app.main import app
from app.services import market_data as market_data_service
from app.services.alpaca_stream import alpaca_stream_url, parse_alpaca_bar, public_alpaca_stream_error
from app.services import news as news_service
from app.services import research as research_service
from app.services import triage as triage_service
from app.services import watchlist as watchlist_service
from app.services.market_data import InsufficientPriceDataError, MarketDataError, RateLimitError, TickerNotFoundError
from app.services.news import NewsArticle, _article_matches_ticker, classify_news, classify_relevance
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


def _quiet_prices() -> pd.DataFrame:
    prices = _prices()
    prices["Open"] = 100.0
    prices["High"] = 101.0
    prices["Low"] = 99.0
    prices["Close"] = 100.0
    prices["Adj Close"] = 100.0
    prices["Volume"] = 1_000_000.0
    return prices


def _news_article(
    title: str,
    *,
    category: str = "guidance",
    impact: int = 4,
    relevance_type: str = "direct",
    is_scoreable: bool = True,
    score_impact: int = 1,
    relevance_reason: str = "direct: Alpha Vantage ticker relevance is high",
) -> NewsArticle:
    return NewsArticle(
        title=title,
        url="https://example.com/news",
        source="Example",
        published_at=datetime(2026, 8, 13, 9, 0, tzinfo=UTC),
        summary="",
        category=category,
        impact=impact,
        relevance_score=0.72 if relevance_type != "ignored" else 0.01,
        ticker_sentiment_score=0.2 if relevance_type == "direct" else None,
        ticker_sentiment_label="Somewhat-Bullish" if relevance_type == "direct" else None,
        overall_sentiment_score=0.1,
        overall_sentiment_label="Neutral",
        relevance_type=relevance_type,
        is_scoreable=is_scoreable,
        score_impact=score_impact,
        relevance_reason=relevance_reason,
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

    response = client.post("/api/research/MISSING/run")

    assert response.status_code == 404
    assert "MISSING" in response.json()["detail"]


def test_research_does_not_expose_provider_api_key_messages(monkeypatch) -> None:
    leaked_message = (
        "We have detected your API key as SECRET and our standard API rate limit is 25 requests per day. "
        "Yahoo fallback is rate-limited: Yahoo Finance rate limit reached."
    )

    def fake_fetch(ticker: str) -> pd.DataFrame:
        raise RateLimitError(leaked_message)

    monkeypatch.setattr(research_service, "fetch_price_data", fake_fetch)

    response = client.post("/api/research/AAPL/run")

    assert response.status_code == 429
    assert response.json()["detail"] == "Market data provider rate limit reached. Try again later."
    assert "SECRET" not in response.text
    assert "API key" not in response.text


def test_compare_does_not_expose_provider_api_key_messages(monkeypatch) -> None:
    leaked_message = "Could not fetch https://example.test/query?apikey=SECRET"

    def fake_fetch(ticker: str) -> pd.DataFrame:
        raise MarketDataError(leaked_message)

    monkeypatch.setattr(compare_route, "fetch_price_data", fake_fetch)

    response = client.get("/api/compare?tickers=AAPL")

    assert response.status_code == 502
    assert response.json()["detail"] == "Market data provider is unavailable. Try again later."
    assert "SECRET" not in response.text
    assert "apikey" not in response.text


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


def test_empty_metadata_cache_expires_quickly() -> None:
    empty_metadata = {
        "name": "AAPL",
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
    provider_metadata = {**empty_metadata, "market_cap": 3_000_000_000_000}

    assert market_data_service._metadata_cache_ttl(empty_metadata) == market_data_service.METADATA_MISS_TTL
    assert market_data_service._metadata_cache_ttl(provider_metadata) == market_data_service.CACHE_TTL


def test_metadata_keeps_last_success_when_refresh_is_empty(monkeypatch) -> None:
    market_data_service._metadata_cache.clear()
    useful_metadata = {
        "name": "Apple Inc.",
        "exchange": "NasdaqGS",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "currency": "USD",
        "market_cap": 3_000_000_000_000,
        "pe_ratio": 31.5,
        "eps": 6.4,
        "revenue_ttm": 390_000_000_000,
        "revenue_growth_yoy": None,
        "profit_margin": 0.24,
        "debt_to_equity": None,
        "dividend_yield": 0.005,
    }
    market_data_service._metadata_cache["AAPL"] = (
        datetime.utcnow() - market_data_service.CACHE_TTL - timedelta(seconds=1),
        useful_metadata,
    )
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test")
    monkeypatch.setattr(market_data_service, "_fetch_company_metadata_from_alphavantage", lambda ticker: {})
    monkeypatch.setattr(market_data_service, "_fetch_company_metadata_from_quote_api", lambda ticker: {})

    try:
        metadata = market_data_service.fetch_company_metadata("AAPL")

        assert metadata["name"] == "Apple Inc."
        assert metadata["market_cap"] == 3_000_000_000_000
        assert metadata["profit_margin"] == 0.24
    finally:
        market_data_service._metadata_cache.clear()


def test_get_research_returns_no_snapshot_without_fetching(monkeypatch) -> None:
    research_service._memory_research_snapshots.clear()

    def fail_fetch(ticker: str) -> pd.DataFrame:
        raise AssertionError("GET /api/research must not fetch provider data")

    monkeypatch.setattr(research_service, "fetch_price_data", fail_fetch)

    response = client.get("/api/research/AAPL")

    assert response.status_code == 200
    assert response.json() == {
        "ticker": "AAPL",
        "status": "no_snapshot",
        "message": "No full check has been run yet.",
    }


def test_research_run_saves_snapshot_for_get(monkeypatch) -> None:
    research_service._memory_research_snapshots.clear()
    monkeypatch.setattr(research_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(research_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(
        research_service,
        "fetch_company_metadata",
        lambda ticker: {
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "currency": "USD",
            "market_cap": 3_000_000_000_000,
            "pe_ratio": 31.5,
            "eps": 6.4,
            "revenue_ttm": None,
            "revenue_growth_yoy": None,
            "profit_margin": None,
            "debt_to_equity": None,
            "dividend_yield": None,
        },
    )

    try:
        run_response = client.post("/api/research/AAPL/run")
        run_body = run_response.json()

        def fail_fetch(ticker: str) -> pd.DataFrame:
            raise AssertionError("GET /api/research must read the saved snapshot")

        monkeypatch.setattr(research_service, "fetch_price_data", fail_fetch)
        read_response = client.get("/api/research/AAPL")
        read_body = read_response.json()

        assert run_response.status_code == 200
        assert read_response.status_code == 200
        assert read_body["ticker"] == "AAPL"
        assert read_body["company_name"] == "Apple Inc."
        assert read_body["price"] == run_body["price"]
        assert read_body["fundamentals"]["market_cap"] == 3_000_000_000_000
        assert read_body["fundamentals"]["pe_ratio"] == 31.5
        assert read_body["signals"]["rsi"] == run_body["signals"]["rsi"]
        assert len(read_body["price_history"]) == 252
        assert read_body["data_source"] == "saved"
    finally:
        research_service._memory_research_snapshots.clear()


def test_research_metadata_merge_preserves_saved_fundamentals_after_provider_miss() -> None:
    saved_metadata = {
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "currency": "USD",
        "market_cap": 3_000_000_000_000,
        "pe_ratio": 31.5,
        "eps": 6.4,
        "revenue_ttm": 390_000_000_000,
        "revenue_growth_yoy": 0.08,
        "profit_margin": 0.25,
        "debt_to_equity": None,
        "dividend_yield": 0.004,
    }

    merged = research_service._merge_saved_metadata(saved_metadata, research_service._empty_metadata("AAPL"), "AAPL")

    assert merged["name"] == "Apple Inc."
    assert merged["sector"] == "Technology"
    assert merged["industry"] == "Consumer Electronics"
    assert merged["market_cap"] == 3_000_000_000_000
    assert merged["revenue_ttm"] == 390_000_000_000


def test_research_metadata_merge_restores_fallback_name_with_partial_fresh_metadata() -> None:
    saved_metadata = {
        **research_service._empty_metadata("AAPL"),
        "name": "Apple Inc.",
        "market_cap": 3_000_000_000_000,
        "pe_ratio": 31.5,
    }
    fresh_metadata = {
        **research_service._empty_metadata("AAPL"),
        "market_cap": 3_100_000_000_000,
    }

    merged = research_service._merge_saved_metadata(saved_metadata, fresh_metadata, "AAPL")

    assert merged["name"] == "Apple Inc."
    assert merged["market_cap"] == 3_100_000_000_000
    assert merged["pe_ratio"] == 31.5


def test_research_metadata_merge_keeps_fresh_valid_name_without_other_fields() -> None:
    saved_metadata = {**research_service._empty_metadata("AAPL"), "name": "Apple Inc."}
    fresh_metadata = {**research_service._empty_metadata("AAPL"), "name": "Apple Incorporated"}

    merged = research_service._merge_saved_metadata(saved_metadata, fresh_metadata, "AAPL")

    assert merged["name"] == "Apple Incorporated"


def test_chart_reads_saved_daily_bars_without_fetching(monkeypatch) -> None:
    research_service._memory_research_snapshots.clear()
    monkeypatch.setattr(research_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(research_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(research_service, "fetch_company_metadata", lambda ticker: research_service._empty_metadata(ticker))

    try:
        run_response = client.post("/api/research/AAPL/run")

        def fail_fetch(ticker: str) -> pd.DataFrame:
            raise AssertionError("GET /api/chart must read saved candles")

        monkeypatch.setattr(research_service, "fetch_price_data", fail_fetch)
        chart_response = client.get("/api/chart/AAPL?range=6m&interval=1d")
        chart = chart_response.json()

        assert run_response.status_code == 200
        assert chart_response.status_code == 200
        assert len(chart) == 126
        assert chart[-1]["close"] == run_response.json()["price"]
    finally:
        research_service._memory_research_snapshots.clear()


def test_parse_alpaca_bar_normalises_live_candle() -> None:
    bar = parse_alpaca_bar(
        {
            "T": "b",
            "S": "aapl",
            "o": 200.1,
            "h": 201.5,
            "l": 199.8,
            "c": 201.0,
            "v": 12345,
            "n": 42,
            "vw": 200.7,
            "t": "2026-08-19T01:23:00Z",
        }
    )

    assert bar == {
        "type": "bar",
        "ticker": "AAPL",
        "timestamp": "2026-08-19T01:23:00Z",
        "open": 200.1,
        "high": 201.5,
        "low": 199.8,
        "close": 201.0,
        "volume": 12345,
        "trade_count": 42,
        "vwap": 200.7,
        "source": "alpaca_iex",
    }


def test_alpaca_stream_url_uses_stock_iex_feed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ALPACA_STREAM_URL", raising=False)
    monkeypatch.delenv("ALPACA_DATA_FEED", raising=False)

    assert alpaca_stream_url() == "wss://stream.data.alpaca.markets/v2/iex"


def test_live_candle_websocket_requires_ticker() -> None:
    with client.websocket_connect("/ws/candles") as websocket:
        assert websocket.receive_json() == {"type": "error", "message": "Valid ticker query parameter is required"}


def test_live_candle_websocket_rejects_invalid_ticker() -> None:
    with client.websocket_connect("/ws/candles?ticker=AAPL<script>") as websocket:
        assert websocket.receive_json() == {"type": "error", "message": "Valid ticker query parameter is required"}


def test_live_candle_websocket_rejects_untrusted_origin() -> None:
    try:
        with client.websocket_connect("/ws/candles?ticker=AAPL", headers={"origin": "https://evil.example"}):
            raise AssertionError("untrusted origin should close before accepting")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008


def test_live_candle_websocket_limits_client_connections(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_CANDLE_CONNECTION_LIMIT", "0")
    candles_route._active_streams_by_client.clear()

    with client.websocket_connect("/ws/candles?ticker=AAPL") as websocket:
        assert websocket.receive_json()["message"] == "Live candle connection limit reached. Close another live chart tab and retry."


def test_public_alpaca_stream_error_hides_provider_message() -> None:
    assert public_alpaca_stream_error(406) == "Live data connection limit reached. Close other live chart tabs and retry."
    assert public_alpaca_stream_error(401) == "Live data provider authentication or subscription failed."
    assert public_alpaca_stream_error("unknown") == "Live data provider is unavailable. Try again later."


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


def test_memory_watchlist_rename_collision_preserves_replacement_check_status() -> None:
    watchlist_service._memory_watchlist.clear()
    checked_at = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)

    try:
        watchlist_service.add_watchlist_item(None, "AAPL")
        watchlist_service.add_watchlist_item(None, "MSFT")
        watchlist_service.update_check_status(
            None,
            "MSFT",
            "data_issue",
            message="Provider could not return enough price history.",
            checked_at=checked_at,
        )

        updated = watchlist_service.update_watchlist_item(None, "AAPL", "MSFT")

        assert updated["ticker"] == "MSFT"
        assert updated["last_check_status"] == "data_issue"
        assert updated["last_check_message"] == "Provider could not return enough price history."
        assert updated["last_checked_at"] == checked_at
    finally:
        watchlist_service._memory_watchlist.clear()


def test_watchlist_note_columns_have_valid_empty_defaults() -> None:
    ddl = str(CreateTable(models.WatchlistItem.__table__).compile(dialect=sqlite.dialect()))

    assert "watch_reason TEXT DEFAULT '' NOT NULL" in ddl
    assert "main_risk TEXT DEFAULT '' NOT NULL" in ddl
    assert "change_my_mind TEXT DEFAULT '' NOT NULL" in ddl
    assert "last_check_status VARCHAR(32)" in ddl
    assert "last_check_message TEXT" in ddl
    assert "last_checked_at DATETIME" in ddl


def test_company_metadata_columns_have_valid_defaults() -> None:
    ddl = str(CreateTable(models.Company.__table__).compile(dialect=sqlite.dialect()))

    assert "currency VARCHAR(12) DEFAULT '' NOT NULL" in ddl
    assert "market_cap BIGINT" in ddl
    assert "pe_ratio FLOAT" in ddl
    assert "dividend_yield FLOAT" in ddl


def test_triage_snapshot_columns_have_defaults_for_existing_databases() -> None:
    ddl = str(CreateTable(models.TriageSnapshot.__table__).compile(dialect=sqlite.dialect()))

    assert "top_news JSON DEFAULT '[]' NOT NULL" in ddl
    assert "price_change_pct FLOAT DEFAULT 0 NOT NULL" in ddl
    assert "as_of_date DATE DEFAULT CURRENT_DATE NOT NULL" in ddl
    assert "volatility_percentile FLOAT DEFAULT 0 NOT NULL" in ddl
    assert "volume_ratio FLOAT DEFAULT 1 NOT NULL" in ddl


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
    monkeypatch.setattr(triage_service, "fetch_ticker_news", lambda ticker, **kwargs: [])

    response = client.post("/api/triage/run?tickers=aapl,msft")
    body = response.json()

    assert response.status_code == 200
    assert [item["ticker"] for item in body["items"]] == ["MSFT", "AAPL"]
    assert body["items"][0]["attention_score"] > body["items"][1]["attention_score"]
    assert body["items"][0]["reasons"]
    assert seen == ["AAPL", "MSFT"]


def test_get_triage_returns_not_checked_watchlist_rows_without_snapshot(monkeypatch) -> None:
    triage_service._memory_triage_snapshots.clear()
    monkeypatch.setattr(
        triage_service,
        "list_watchlist",
        lambda db: [
            {
                "ticker": "BHP.AX",
                "created_at": datetime(2026, 8, 14, tzinfo=UTC),
                "signal": "Tracked",
                "watch_reason": "Iron ore cash flow.",
                "main_risk": "",
                "change_my_mind": "",
                "last_check_status": None,
                "last_check_message": None,
                "last_checked_at": None,
            }
        ],
    )

    try:
        response = client.get("/api/triage")
        item = response.json()["items"][0]

        assert response.status_code == 200
        assert item["ticker"] == "BHP.AX"
        assert item["status"] == "not_checked"
        assert item["attention_score"] is None
        assert item["severity"] is None
        assert item["issue_message"] == "Run Check to create the first snapshot."
        assert item["watch_note"]["watch_reason"] == "Iron ore cash flow."
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_triage_run_returns_data_issue_without_fake_snapshot(monkeypatch) -> None:
    triage_service._memory_triage_snapshots.clear()
    monkeypatch.setattr(
        triage_service,
        "list_watchlist",
        lambda db: [
            {
                "ticker": "BHP.AX",
                "created_at": datetime(2026, 8, 14, tzinfo=UTC),
                "signal": "Tracked",
                "watch_reason": "",
                "main_risk": "",
                "change_my_mind": "",
                "last_check_status": None,
                "last_check_message": None,
                "last_checked_at": None,
            }
        ],
    )

    def fail_fetch(ticker: str) -> pd.DataFrame:
        raise InsufficientPriceDataError("raw provider details")

    monkeypatch.setattr(triage_service, "fetch_price_data", fail_fetch)

    try:
        response = client.post("/api/triage/run")
        item = response.json()["items"][0]

        assert response.status_code == 200
        assert item["status"] == "data_issue"
        assert item["attention_score"] is None
        assert item["price"] is None
        assert item["issue_message"] == "Provider could not return enough price history."
        assert triage_service._memory_triage_snapshots == {}
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_triage_adds_price_relevant_news(monkeypatch) -> None:
    def fake_news(ticker: str, **kwargs) -> list[NewsArticle]:
        return [_news_article(f"{ticker} cuts revenue guidance after weak demand")]

    monkeypatch.setattr(triage_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(triage_service, "fetch_ticker_news", fake_news)

    response = client.post("/api/triage/run?tickers=aapl")
    item = response.json()["items"][0]

    assert response.status_code == 200
    assert item["news"][0]["category"] == "guidance"
    assert item["news"][0]["is_scoreable"] is True
    assert item["news"][0]["score_impact"] == 36
    assert any(reason["code"] == "news" for reason in item["reasons"])
    assert item["attention_score"] >= 60


def test_direct_news_scores_without_price_confirmation() -> None:
    without_news = triage_service.score_ticker("AAPL", _prices(), [])
    with_news = triage_service.score_ticker("AAPL", _prices(), [_news_article("AAPL cuts revenue guidance")])

    assert with_news.news[0].relevance_type == "direct"
    assert with_news.news[0].is_scoreable is True
    assert with_news.news[0].score_impact == 36
    assert with_news.attention_score == min(100, without_news.attention_score + 36)


def test_sector_context_news_does_not_score_without_confirmation() -> None:
    item = triage_service.score_ticker(
        "AAPL",
        _quiet_prices(),
        [
            _news_article(
                "Broadcom beats expectations as AI chip demand grows",
                relevance_type="sector_context",
                is_scoreable=False,
                score_impact=0,
                relevance_reason="display-only: related peer or sector theme",
            )
        ],
    )

    assert item.news[0].relevance_type == "sector_context"
    assert item.news[0].is_scoreable is False
    assert item.news[0].score_impact == 0
    assert item.news[0].relevance_reason == "display-only: no price/volume confirmation"
    assert not any(reason.code == "news" for reason in item.reasons)


def test_sector_context_news_scores_with_price_volume_confirmation() -> None:
    prices = _prices()
    prices.iloc[-1, prices.columns.get_loc("Volume")] = prices["Volume"].iloc[-1] * 3

    item = triage_service.score_ticker(
        "AAPL",
        prices,
        [
            _news_article(
                "Broadcom beats expectations as AI chip demand grows",
                relevance_type="sector_context",
                is_scoreable=False,
                score_impact=0,
                relevance_reason="display-only: related peer or sector theme",
            )
        ],
    )

    assert item.news[0].relevance_type == "sector_context"
    assert item.news[0].is_scoreable is True
    assert item.news[0].score_impact == 12
    assert "confirmed by price/volume movement" in item.news[0].relevance_reason
    assert any(reason.code == "news" for reason in item.reasons)


def test_ignored_news_never_scores() -> None:
    item = triage_service.score_ticker(
        "AAPL",
        _prices(),
        [
            _news_article(
                "Envista receives analyst upgrade",
                relevance_type="ignored",
                is_scoreable=False,
                score_impact=0,
                relevance_reason="ignored: low ticker relevance",
            )
        ],
    )

    assert item.news[0].relevance_type == "ignored"
    assert item.news[0].score_impact == 0
    assert not any(reason.code == "news" for reason in item.reasons)


def test_triage_snapshot_caps_and_preserves_debug_news() -> None:
    articles = [
        *[_news_article(f"AAPL direct guidance {index}") for index in range(7)],
        *[
            _news_article(
                f"Broadcom sector context {index}",
                relevance_type="sector_context",
                is_scoreable=False,
                score_impact=0,
                relevance_reason="display-only: related peer or sector theme",
            )
            for index in range(7)
        ],
        *[
            _news_article(
                f"Ignored article {index}",
                relevance_type="ignored",
                is_scoreable=False,
                score_impact=0,
                relevance_reason="ignored: low ticker relevance",
            )
            for index in range(5)
        ],
    ]
    item = triage_service.score_ticker("AAPL", _quiet_prices(), articles)
    payload = triage_service._snapshot_payload(item)
    saved_news = payload["top_news"]

    assert len(saved_news) == 13
    assert len([article for article in saved_news if article["is_scoreable"]]) == 5
    assert len([article for article in saved_news if article["relevance_type"] == "sector_context"]) == 5
    assert len([article for article in saved_news if article["relevance_type"] == "ignored"]) == 3
    assert saved_news[0]["score_impact"] == 36
    assert saved_news[0]["ticker_sentiment_label"] == "Somewhat-Bullish"


def test_triage_snapshot_prioritises_direct_news_over_sector_context() -> None:
    prices = _prices()
    prices.iloc[-1, prices.columns.get_loc("Volume")] = prices["Volume"].iloc[-1] * 3
    articles = [
        *[
            _news_article(
                f"Sector context {index}",
                relevance_type="sector_context",
                is_scoreable=True,
                score_impact=12,
                relevance_reason="display-only: related peer or sector theme; confirmed by price/volume movement",
            )
            for index in range(6)
        ],
        _news_article(
            "PLTR appoints new executive",
            category="management",
            impact=2,
            relevance_type="direct",
            is_scoreable=True,
            score_impact=12,
            relevance_reason="direct: target ticker relevance is high and headline mentions the company",
        ),
    ]
    item = triage_service.score_ticker("PLTR", prices, articles)
    saved_news = triage_service._snapshot_payload(item)["top_news"]

    assert len([article for article in saved_news if article["is_scoreable"]]) == 5
    assert any(article["title"] == "PLTR appoints new executive" for article in saved_news)


def test_get_triage_returns_news_saved_by_run(monkeypatch) -> None:
    def fake_news(ticker: str, **kwargs) -> list[NewsArticle]:
        return [_news_article(f"{ticker} raises revenue guidance")]

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
        assert read_item["news"][0]["relevance_type"] == "direct"
        assert read_item["news"][0]["score_impact"] == 36
        assert read_item["price_change_pct"] == run_response.json()["items"][0]["price_change_pct"]
        assert read_item["as_of_date"] == run_response.json()["items"][0]["as_of_date"]
        assert read_item["news_issue_message"] is None
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_run_triage_surfaces_news_provider_issue(monkeypatch) -> None:
    triage_service._memory_triage_snapshots.clear()
    monkeypatch.setattr(triage_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)

    def rate_limited_news(ticker: str, **kwargs) -> list[NewsArticle]:
        raise RateLimitError("free api requests reached")

    monkeypatch.setattr(triage_service, "fetch_ticker_news", rate_limited_news)

    try:
        run_response = client.post("/api/triage/run?tickers=msft")
        read_response = client.get("/api/triage?tickers=msft")
        run_item = run_response.json()["items"][0]
        read_item = read_response.json()["items"][0]

        assert run_response.status_code == 200
        assert run_item["status"] == "ok"
        assert run_item["news"] == []
        assert run_item["news_issue_message"] == "News provider rate limit was reached for this check."
        assert read_response.status_code == 200
        assert read_item["news_issue_message"] == run_item["news_issue_message"]
    finally:
        triage_service._memory_triage_snapshots.clear()


def test_triage_includes_watch_notes(monkeypatch) -> None:
    monkeypatch.setattr(triage_service, "fetch_price_data", lambda ticker: _prices())
    monkeypatch.setattr(triage_service, "clean_price_data", lambda df: df)
    monkeypatch.setattr(triage_service, "fetch_ticker_news", lambda ticker, **kwargs: [])
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
    monkeypatch.setattr(triage_service, "fetch_ticker_news", lambda ticker, **kwargs: [])

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
            "top_news": [
                {
                    "title": "MSFT raises cloud guidance",
                    "url": "https://example.com/msft",
                    "source": "Example",
                    "published_at": "2026-08-14T08:30:00Z",
                    "category": "guidance",
                    "impact": 4,
                },
                {
                    "title": "Bad legacy timestamp",
                    "url": "https://example.com/bad",
                    "source": "Example",
                    "published_at": "not-a-date",
                    "category": "guidance",
                    "impact": 4,
                },
            ],
            "price": 410.0,
            "price_change_pct": -0.021,
            "as_of_date": "2026-08-14",
            "volume": 1200000.0,
            "volatility_percentile": 0.72,
            "volume_ratio": 1.8,
            "rsi": 55.0,
            "moving_average_status": "above_both",
            "created_at": datetime(2026, 8, 14, 9, 0),
        }
    ]

    def fail_fetch(ticker: str) -> pd.DataFrame:
        raise AssertionError("GET /api/triage must not fetch live market data")

    monkeypatch.setattr(triage_service, "fetch_price_data", fail_fetch)

    try:
        response = client.get("/api/triage?tickers=msft")
        body = response.json()

        assert response.status_code == 200
        assert datetime.fromisoformat(body["generated_at"].replace("Z", "+00:00")).tzinfo is not None
        assert body["items"][0]["ticker"] == "MSFT"
        assert body["items"][0]["attention_score"] == 24
        assert body["items"][0]["price_change_pct"] == -0.021
        assert body["items"][0]["as_of_date"] == "2026-08-14"
        assert body["items"][0]["metrics"]["volatility_percentile"] == 0.72
        assert body["items"][0]["metrics"]["volume_ratio"] == 1.8
        assert [article["title"] for article in body["items"][0]["news"]] == ["MSFT raises cloud guidance"]
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


def test_news_relevance_classifies_direct_ticker_articles() -> None:
    result = classify_relevance(
        "AAPL",
        {
            "ticker_sentiment": [
                {
                    "ticker": "AAPL",
                    "relevance_score": "0.84",
                    "ticker_sentiment_score": "0.31",
                    "ticker_sentiment_label": "Bullish",
                }
            ]
        },
        "Apple raises iPhone revenue guidance",
        "",
    )

    assert result["relevance_type"] == "direct"
    assert result["is_scoreable"] is False
    assert result["score_impact"] == 0
    assert result["relevance_score"] == 0.84
    assert result["ticker_sentiment_score"] == 0.31
    assert result["ticker_sentiment_label"] == "Bullish"


def test_news_relevance_classifies_sector_context_articles() -> None:
    result = classify_relevance(
        "AAPL",
        {"ticker_sentiment": [{"ticker": "AVGO", "relevance_score": "0.63"}]},
        "Broadcom beats expectations as AI chip demand grows",
        "",
    )

    assert result["relevance_type"] == "sector_context"
    assert result["is_scoreable"] is False
    assert result["score_impact"] == 0
    assert "display-only" in result["relevance_reason"]


def test_news_relevance_ignores_unrelated_or_background_articles() -> None:
    unrelated = classify_relevance("AAPL", {"ticker_sentiment": [{"ticker": "ENV"}]}, "Envista receives analyst upgrade", "")
    evergreen = classify_relevance(
        "AAPL",
        {"ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "0.9"}]},
        "Apple Inc. history, products, and headquarters",
        "",
    )

    assert unrelated["relevance_type"] == "ignored"
    assert unrelated["is_scoreable"] is False
    assert unrelated["score_impact"] == 0
    assert evergreen["relevance_type"] == "ignored"
    assert "evergreen" in evergreen["relevance_reason"]


def test_news_relevance_unknown_ticker_requires_direct_provider_relevance() -> None:
    weak_unknown = classify_relevance(
        "XYZ",
        {"ticker_sentiment": [{"ticker": "ABC", "relevance_score": "0.7"}]},
        "Semiconductor demand improves across the sector",
        "",
    )
    direct_unknown = classify_relevance(
        "XYZ",
        {"ticker_sentiment": [{"ticker": "XYZ", "relevance_score": "0.61"}]},
        "XYZ reports quarterly results",
        "",
    )

    assert weak_unknown["relevance_type"] == "ignored"
    assert "no ticker context" in weak_unknown["relevance_reason"]
    assert direct_unknown["relevance_type"] == "direct"


def test_news_endpoint_returns_classified_articles(monkeypatch) -> None:
    def fake_news(ticker: str, *, limit: int = 5, lookback=None, raise_on_error: bool = False) -> list[NewsArticle]:
        return [
            NewsArticle(
                title=f"{ticker} receives analyst upgrade",
                url="https://example.com/upgrade",
                source="Example",
                published_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
                summary="",
                category="analyst",
                impact=2,
                relevance_score=0.72,
                ticker_sentiment_score=0.2,
                ticker_sentiment_label="Somewhat-Bullish",
                overall_sentiment_score=0.1,
                overall_sentiment_label="Neutral",
                relevance_type="direct",
                is_scoreable=True,
                score_impact=12,
                relevance_reason="direct: Alpha Vantage ticker relevance is high",
            )
        ][:limit]

    monkeypatch.setattr("app.api.routes.news.fetch_ticker_news", fake_news)

    response = client.get("/api/news/aapl?limit=1&lookback_hours=48")

    assert response.status_code == 200
    assert response.json()[0]["category"] == "analyst"
    assert response.json()[0]["impact"] == 2
    assert response.json()[0]["relevance_type"] == "direct"
    assert response.json()[0]["is_scoreable"] is True
    assert response.json()[0]["score_impact"] == 12
    assert response.json()[0]["ticker_sentiment_label"] == "Somewhat-Bullish"


def test_news_endpoint_reports_missing_provider_key(monkeypatch) -> None:
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    news_service._news_cache.clear()

    try:
        response = client.get("/api/news/aapl")

        assert response.status_code == 503
        assert response.json()["detail"] == "Set ALPHAVANTAGE_API_KEY to enable ticker news."
    finally:
        news_service._news_cache.clear()


def test_news_endpoint_reports_provider_rate_limit(monkeypatch) -> None:
    news_service._news_cache.clear()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test")

    def rate_limited(ticker: str, *, lookback) -> list[NewsArticle]:
        raise RateLimitError("free api requests reached")

    monkeypatch.setattr(news_service, "_fetch_alphavantage_news", rate_limited)

    try:
        response = client.get("/api/news/aapl")

        assert response.status_code == 429
        assert response.json()["detail"] == "News provider rate limit reached. Try again later."
    finally:
        news_service._news_cache.clear()


def test_news_endpoint_does_not_expose_provider_api_key_messages(monkeypatch) -> None:
    news_service._news_cache.clear()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "SECRET_TOKEN")

    def provider_failed(ticker: str, *, lookback) -> list[NewsArticle]:
        raise MarketDataError("We have detected your API key as SECRET_TOKEN for this account.")

    monkeypatch.setattr(news_service, "_fetch_alphavantage_news", provider_failed)

    try:
        response = client.get("/api/news/aapl")

        assert response.status_code == 503
        assert response.json()["detail"] == "News provider is unavailable. Try again later."
        assert "SECRET_TOKEN" not in response.text
        assert "API key" not in response.text
    finally:
        news_service._news_cache.clear()


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


def test_news_fetch_errors_are_not_cached_as_empty_results(monkeypatch) -> None:
    news_service._news_cache.clear()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test")

    def rate_limited(ticker: str, *, lookback) -> list[NewsArticle]:
        raise RateLimitError("free api requests reached")

    monkeypatch.setattr(news_service, "_fetch_alphavantage_news", rate_limited)

    try:
        assert news_service.fetch_ticker_news("aapl") == []
        assert news_service._news_cache == {}
    finally:
        news_service._news_cache.clear()
