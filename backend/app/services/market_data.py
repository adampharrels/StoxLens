import os
from datetime import datetime, timedelta

import pandas as pd
from requests import HTTPError

ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"
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
METADATA_MISS_TTL = timedelta(minutes=1)
_price_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
_metadata_cache: dict[str, tuple[datetime, dict]] = {}


class MarketDataError(Exception):
    pass


class RateLimitError(MarketDataError):
    pass


class TickerNotFoundError(MarketDataError):
    pass


class AlphaVantageRateLimitError(RateLimitError):
    pass


class YahooRateLimitError(RateLimitError):
    pass


class InsufficientPriceDataError(MarketDataError):
    pass


def public_market_data_error(exc: MarketDataError) -> str:
    if isinstance(exc, RateLimitError):
        return "Market data provider rate limit reached. Try again later."
    return "Market data provider is unavailable. Try again later."


def fetch_price_data(ticker: str) -> pd.DataFrame:
    key = ticker.upper()
    cached = _price_cache.get(key)
    if cached and datetime.utcnow() - cached[0] < CACHE_TTL:
        return cached[1].copy()

    df = _fetch_price_data(key)
    _price_cache[key] = (datetime.utcnow(), df.copy())
    return df


def _fetch_price_data(ticker: str) -> pd.DataFrame:
    if not _alphavantage_api_key():
        return _fetch_price_data_from_chart_api(ticker)

    try:
        return _fetch_price_data_from_alphavantage(ticker)
    except MarketDataError as alpha_error:
        try:
            return _fetch_price_data_from_chart_api(ticker)
        except TickerNotFoundError as yahoo_error:
            raise TickerNotFoundError(f"{alpha_error}. Yahoo fallback also found no data: {yahoo_error}") from yahoo_error
        except RateLimitError as yahoo_error:
            raise RateLimitError(f"{alpha_error}. Yahoo fallback is rate-limited: {yahoo_error}") from yahoo_error
        except MarketDataError as yahoo_error:
            raise MarketDataError(
                f"Alpha Vantage failed for {ticker.upper()} ({_alphavantage_symbol(ticker)}): {alpha_error}. "
                f"Yahoo fallback also failed: {yahoo_error}"
            ) from yahoo_error


def _alphavantage_api_key() -> str | None:
    return os.getenv("ALPHAVANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_API_KEY")


def market_data_source() -> str:
    return "Alpha Vantage" if _alphavantage_api_key() else "Yahoo Finance"


def _alphavantage_symbol(ticker: str) -> str:
    if ticker.endswith(".AX"):
        return f"{ticker[:-3]}.AUS"
    return ticker


def _fetch_price_data_from_alphavantage(ticker: str) -> pd.DataFrame:
    api_key = _alphavantage_api_key()
    if not api_key:
        raise MarketDataError("ALPHAVANTAGE_API_KEY is not configured")

    symbol = _alphavantage_symbol(ticker)
    payload = _get_alphavantage_payload(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": os.getenv("ALPHAVANTAGE_OUTPUTSIZE", "compact"),
            "apikey": api_key,
        }
    )
    return _alphavantage_time_series_to_frame(ticker, symbol, payload)


def _get_alphavantage_payload(params: dict[str, str]) -> dict:
    try:
        import requests

        response = requests.get(ALPHAVANTAGE_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise MarketDataError("Could not fetch Alpha Vantage data") from exc

    if "Error Message" in payload:
        raise TickerNotFoundError(payload["Error Message"])

    note = payload.get("Note") or payload.get("Information")
    if note:
        lowered = str(note).lower()
        if "rate limit" in lowered or "free api requests" in lowered:
            raise AlphaVantageRateLimitError(str(note))
        raise MarketDataError(str(note))

    return payload


def _alphavantage_time_series_to_frame(ticker: str, symbol: str, payload: dict) -> pd.DataFrame:
    series = payload.get("Time Series (Daily)")
    if not series:
        raise TickerNotFoundError(f"No Alpha Vantage daily price data found for {ticker.upper()} ({symbol})")

    rows = []
    for date, values in series.items():
        rows.append(
            {
                "Date": date,
                "Open": _float_value(values, "1. open"),
                "High": _float_value(values, "2. high"),
                "Low": _float_value(values, "3. low"),
                "Close": _float_value(values, "4. close"),
                "Volume": _int_value(values, "6. volume") or _int_value(values, "5. volume"),
                "Adj Close": _float_value(values, "5. adjusted close") or _float_value(values, "4. close"),
            }
        )

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    return df


def _float_value(values: dict, key: str) -> float | None:
    raw = values.get(key)
    return float(raw) if raw not in (None, "") else None


def _int_value(values: dict, key: str) -> int | None:
    raw = values.get(key)
    return int(raw) if raw not in (None, "") else None


def _optional_float(value: object) -> float | None:
    if value in (None, "", "None", "N/A", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    parsed = _optional_float(value)
    return int(parsed) if parsed is not None else None


def _fetch_price_data_from_chart_api(ticker: str) -> pd.DataFrame:
    last_error: Exception | None = None
    for host in YAHOO_CHART_HOSTS:
        try:
            payload = _get_yahoo_chart_payload(host, ticker)
            return _chart_payload_to_frame(ticker, payload)
        except TickerNotFoundError:
            raise
        except YahooRateLimitError as exc:
            last_error = exc
        except MarketDataError as exc:
            last_error = exc
    if last_error:
        if isinstance(last_error, YahooRateLimitError):
            raise last_error
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
                raise YahooRateLimitError("Yahoo Finance rate limit reached. Wait a few minutes and retry.") from exc
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
    if len(cleaned) < 90:
        raise InsufficientPriceDataError("At least 90 clean trading days are required for signal calculations")
    cleaned.index = pd.to_datetime(cleaned.index)
    return cleaned


def fetch_company_metadata(ticker: str) -> dict:
    key = ticker.upper()
    cached = _metadata_cache.get(key)
    if cached and datetime.utcnow() - cached[0] < _metadata_cache_ttl(cached[1]):
        return cached[1].copy()

    info = _fetch_company_metadata_from_alphavantage(key) if _alphavantage_api_key() else {}
    if not info:
        info = _fetch_company_metadata_from_quote_api(key)
    if info:
        _metadata_cache[key] = (datetime.utcnow(), info.copy())
        return info

    # Keep the last useful fundamentals instead of replacing them with a temporary provider miss.
    if cached and _metadata_cache_ttl(cached[1]) == CACHE_TTL:
        return cached[1].copy()

    fallback = {
        "name": key,
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
    _metadata_cache[key] = (datetime.utcnow(), fallback.copy())
    return fallback


def _metadata_cache_ttl(info: dict) -> timedelta:
    fundamental_keys = (
        "market_cap",
        "pe_ratio",
        "eps",
        "revenue_ttm",
        "revenue_growth_yoy",
        "profit_margin",
        "debt_to_equity",
        "dividend_yield",
    )
    # Empty fallback metadata should be retried soon; real provider data can be cached longer.
    has_fundamentals = any(info.get(key) is not None for key in fundamental_keys)
    has_company_context = bool(info.get("exchange")) or bool(info.get("industry"))
    return CACHE_TTL if has_fundamentals or has_company_context else METADATA_MISS_TTL


def _fetch_company_metadata_from_alphavantage(ticker: str) -> dict:
    api_key = _alphavantage_api_key()
    if not api_key:
        return {}

    try:
        payload = _get_alphavantage_payload(
            {
                "function": "OVERVIEW",
                "symbol": _alphavantage_symbol(ticker),
                "apikey": api_key,
            }
        )
    except MarketDataError:
        return {}

    if not payload or not payload.get("Symbol"):
        return {}

    return {
        "name": payload.get("Name") or ticker.upper(),
        "exchange": payload.get("Exchange") or "",
        "sector": payload.get("Sector") or "Equity",
        "industry": payload.get("Industry") or "",
        "currency": payload.get("Currency") or "",
        "market_cap": _optional_int(payload.get("MarketCapitalization")),
        "pe_ratio": _optional_float(payload.get("PERatio")),
        "eps": _optional_float(payload.get("EPS")),
        "revenue_ttm": _optional_int(payload.get("RevenueTTM")),
        "revenue_growth_yoy": _optional_float(payload.get("QuarterlyRevenueGrowthYOY")),
        "profit_margin": _optional_float(payload.get("ProfitMargin")),
        "debt_to_equity": _optional_float(payload.get("DebtEquityRatio") or payload.get("DebtToEquityRatio")),
        "dividend_yield": _optional_float(payload.get("DividendYield")),
    }


def _fetch_company_metadata_from_quote_api(ticker: str) -> dict:
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
        "market_cap": _optional_int(quote.get("marketCap")),
        "pe_ratio": _optional_float(quote.get("trailingPE") or quote.get("forwardPE")),
        "eps": _optional_float(quote.get("epsTrailingTwelveMonths") or quote.get("epsForward")),
        "revenue_ttm": None,
        "revenue_growth_yoy": None,
        "profit_margin": None,
        "debt_to_equity": None,
        "dividend_yield": _optional_float(quote.get("trailingAnnualDividendYield") or quote.get("dividendYield")),
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
