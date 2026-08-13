import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.market_data import ALPHAVANTAGE_URL, MarketDataError, RateLimitError

NEWS_CACHE_TTL = timedelta(minutes=30)
NEWS_LOOKBACK = timedelta(hours=168)
_news_cache: dict[str, tuple[datetime, list["NewsArticle"]]] = {}


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str
    category: str
    impact: int


KEYWORD_RULES: list[tuple[str, int, tuple[str, ...]]] = [
    ("earnings", 4, ("earnings", "results", "quarterly", "profit", "revenue", "eps")),
    ("guidance", 4, ("guidance", "forecast", "outlook", "warns", "warning", "cuts forecast", "raises forecast")),
    ("regulatory", 4, ("regulator", "regulatory", "lawsuit", "probe", "investigation", "antitrust", "sec", "ban", "restriction")),
    ("m&a", 3, ("acquisition", "merger", "takeover", "buyout", "deal", "stake")),
    ("analyst", 2, ("upgrade", "downgrade", "price target", "initiates", "rating")),
    ("capital return", 2, ("buyback", "repurchase", "dividend", "split")),
    ("management", 2, ("ceo", "cfo", "resigns", "steps down", "appointed", "layoffs", "job cuts")),
    ("product", 1, ("launch", "unveils", "announces", "partnership", "contract", "order")),
]


def fetch_ticker_news(ticker: str, *, limit: int = 5, lookback: timedelta = NEWS_LOOKBACK) -> list[NewsArticle]:
    key = ticker.upper()
    cache_key = f"{key}:{int(lookback.total_seconds())}"
    cached = _news_cache.get(cache_key)
    now = datetime.now(UTC)
    if cached and now - cached[0] < NEWS_CACHE_TTL:
        return cached[1][:limit]

    try:
        articles = _fetch_alphavantage_news(key, lookback=lookback)
    except (MarketDataError, RateLimitError):
        articles = []

    _news_cache[cache_key] = (now, articles)
    return articles[:limit]


def classify_news(title: str, summary: str = "") -> tuple[str, int]:
    text = f"{title} {summary}".lower()
    for category, impact, keywords in KEYWORD_RULES:
        if any(keyword in text for keyword in keywords):
            return category, impact
    return "general", 0


def _fetch_alphavantage_news(ticker: str, *, lookback: timedelta) -> list[NewsArticle]:
    api_key = os.getenv("ALPHAVANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        return []

    try:
        import requests

        response = requests.get(
            ALPHAVANTAGE_URL,
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "sort": "LATEST",
                "limit": "20",
                "apikey": api_key,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise MarketDataError(f"Could not fetch news for {ticker}") from exc

    note = payload.get("Note") or payload.get("Information")
    if note:
        lowered = str(note).lower()
        if "rate limit" in lowered or "free api requests" in lowered:
            raise RateLimitError(str(note))
        raise MarketDataError(str(note))

    cutoff = datetime.now(UTC) - lookback
    articles: list[NewsArticle] = []
    for item in payload.get("feed", []):
        if not _article_matches_ticker(item, ticker):
            continue

        published_at = _parse_alphavantage_time(str(item.get("time_published", "")))
        if published_at is None or published_at < cutoff:
            continue

        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not title:
            continue

        category, impact = classify_news(title, summary)
        if impact <= 0:
            continue

        articles.append(
            NewsArticle(
                title=title,
                url=str(item.get("url") or ""),
                source=str(item.get("source") or "News"),
                published_at=published_at,
                summary=summary,
                category=category,
                impact=impact,
            )
        )

    return articles


def _article_matches_ticker(item: dict, ticker: str) -> bool:
    expected = ticker.upper()
    for sentiment in item.get("ticker_sentiment", []):
        if str(sentiment.get("ticker", "")).upper() == expected:
            return True

    text = f"{item.get('title', '')} {item.get('summary', '')}".upper()
    return f"${expected}" in text or f" {expected} " in f" {text} "


def _parse_alphavantage_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None
