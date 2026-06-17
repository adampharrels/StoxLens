from datetime import datetime, timedelta

import pandas as pd
from requests import HTTPError

YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}
YAHOO_CHART_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
CACHE_TTL = timedelta(minutes=15)
_price_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
_metadata_cache: dict[str, tuple[datetime, dict[str, str]]] = {}


class MarketDataError(Exception):
    pass


class TickerNotFoundError(MarketDataError):
    pass


class InsufficientPriceDataError(MarketDataError):
    pass


def fetch_price_data(ticker: str) -> pd.DataFrame:
    key = ticker.upper()
    cached = _price_cache.get(key)
    if cached and datetime.utcnow() - cached[0] < CACHE_TTL:
        return cached[1].copy()

    df = _fetch_price_data_from_chart_api(key)
    _price_cache[key] = (datetime.utcnow(), df.copy())
    return df


def _fetch_price_data_from_chart_api(ticker: str) -> pd.DataFrame:
    last_error: Exception | None = None
    for host in YAHOO_CHART_HOSTS:
        try:
            payload = _get_yahoo_chart_payload(host, ticker)
            return _chart_payload_to_frame(ticker, payload)
        except TickerNotFoundError:
            raise
        except MarketDataError as exc:
            last_error = exc
    if last_error:
        raise MarketDataError(str(last_error)) from last_error
    raise MarketDataError(f"Could not fetch Yahoo chart data for {ticker.upper()}")


def _get_yahoo_chart_payload(host: str, ticker: str) -> dict:
    try:
        import requests

        response = requests.get(
            f"https://{host}/v8/finance/chart/{ticker}",
            params={
                "range": "5y",
                "interval": "1d",
                "events": "history",
                "includeAdjustedClose": "true",
            },
            headers=YAHOO_HEADERS,
            timeout=12,
        )
        try:
            response.raise_for_status()
        except HTTPError as exc:
            if response.status_code == 429:
                raise MarketDataError("Yahoo Finance rate limit reached. Wait a few minutes and retry.") from exc
            raise
        return response.json()
    except Exception as exc:
        if isinstance(exc, MarketDataError):
            raise
        raise MarketDataError(f"Could not fetch Yahoo chart data for {ticker.upper()} from {host}") from exc


def _chart_payload_to_frame(ticker: str, payload: dict) -> pd.DataFrame:
    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        raise TickerNotFoundError(error.get("description") or f"No Yahoo Finance price data found for {ticker.upper()}")

    results = chart.get("result") or []
    if not results:
        raise TickerNotFoundError(f"No Yahoo Finance price data found for {ticker.upper()}")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")

    if not timestamps or not quote:
        raise TickerNotFoundError(f"No Yahoo Finance price data found for {ticker.upper()}")

    size = len(timestamps)
    dates = pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None).normalize()
    close = _series_values(quote.get("close"), size)
    df = pd.DataFrame(
        {
            "Open": _series_values(quote.get("open"), size),
            "High": _series_values(quote.get("high"), size),
            "Low": _series_values(quote.get("low"), size),
            "Close": close,
            "Volume": _series_values(quote.get("volume"), size),
            "Adj Close": _series_values(adjusted, size) if adjusted else close,
        },
        index=dates,
    )
    return df


def _series_values(values: list | None, size: int) -> list:
    if values is None:
        return [None] * size
    return values


def clean_price_data(df: pd.DataFrame) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close", "Volume", "Adj Close"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise MarketDataError(f"Missing required price columns: {', '.join(missing)}")

    cleaned = df.copy()
    cleaned = cleaned[required]
    cleaned = cleaned.ffill(limit=2).dropna()
    if len(cleaned) < 252:
        raise InsufficientPriceDataError("At least 252 clean trading days are required for signal calculations")
    cleaned.index = pd.to_datetime(cleaned.index)
    return cleaned


def fetch_company_metadata(ticker: str) -> dict[str, str]:
    key = ticker.upper()
    cached = _metadata_cache.get(key)
    if cached and datetime.utcnow() - cached[0] < CACHE_TTL:
        return cached[1].copy()

    info = _fetch_company_metadata_from_quote_api(key)
    if info:
        _metadata_cache[key] = (datetime.utcnow(), info.copy())
        return info

    fallback = {
        "name": key,
        "exchange": "",
        "sector": "Equity",
        "industry": "",
        "currency": "",
    }
    _metadata_cache[key] = (datetime.utcnow(), fallback.copy())
    return fallback


def _fetch_company_metadata_from_quote_api(ticker: str) -> dict[str, str]:
    try:
        import requests

        response = requests.get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            params={"symbols": ticker},
            headers=YAHOO_HEADERS,
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}

    results = payload.get("quoteResponse", {}).get("result") or []
    if not results:
        return {}

    quote = results[0]
    return {
        "name": quote.get("longName") or quote.get("shortName") or ticker.upper(),
        "exchange": quote.get("fullExchangeName") or quote.get("exchange") or "",
        "sector": quote.get("sector") or quote.get("quoteType") or "Equity",
        "industry": quote.get("industry") or "",
        "currency": quote.get("currency") or "",
    }


def assess_data_quality(df: pd.DataFrame) -> dict[str, int | bool | str]:
    expected = len(pd.bdate_range(start=df.index.min(), end=df.index.max()))
    missing = max(expected - len(df), 0)
    completeness = round(len(df) / expected, 4) if expected else 0
    score = 5
    if completeness < 0.98:
        score -= 1
    if missing > 10:
        score -= 1
    if len(df) < 252:
        score -= 2
    return {
        "completeness": completeness,
        "gap_count": missing,
        "adjusted_prices": "Adj Close" in df.columns,
        "trading_days": len(df),
        "score": max(score, 1),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
