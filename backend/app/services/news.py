import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.market_data import ALPHAVANTAGE_URL, MarketDataError, RateLimitError

NEWS_CACHE_TTL = timedelta(minutes=30)
NEWS_LOOKBACK = timedelta(hours=168)
_news_cache: dict[str, tuple[datetime, list["NewsArticle"]]] = {}


@dataclass
class TickerContext:
    ticker: str
    aliases: tuple[str, ...] = ()
    themes: tuple[str, ...] = ()
    peers: tuple[str, ...] = ()
    allow_sector_guessing: bool = False


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str
    category: str
    impact: int
    relevance_score: float | None = None
    ticker_sentiment_score: float | None = None
    ticker_sentiment_label: str | None = None
    overall_sentiment_score: float | None = None
    overall_sentiment_label: str | None = None
    relevance_type: str = "ignored"
    is_scoreable: bool = False
    score_impact: int = 0
    relevance_reason: str = "ignored: relevance was not assessed"


class NewsUnavailableError(RuntimeError):
    pass


class NewsProviderConfigError(MarketDataError):
    pass


KEYWORD_RULES: list[tuple[str, int, tuple[str, ...]]] = [
    ("earnings", 4, ("earnings", "results", "quarterly", "profit", "revenue", "eps")),
    ("guidance", 4, ("guidance", "forecast", "outlook", "warns", "warning", "cuts forecast", "raises forecast")),
    ("regulatory", 4, ("regulator", "regulatory", "lawsuit", "probe", "investigation", "antitrust", "sec", "ban", "restriction")),
    ("m&a", 3, ("m&a", "acquisition", "merger", "takeover", "buyout", "deal", "stake")),
    ("analyst", 2, ("upgrade", "downgrade", "price target", "initiates", "rating")),
    ("capital return", 2, ("buyback", "repurchase", "dividend", "split")),
    ("management", 2, ("ceo", "cfo", "resigns", "steps down", "appointed", "layoffs", "job cuts")),
    ("product", 1, ("launch", "unveils", "announces", "partnership", "contract", "order")),
]

TICKER_CONTEXT: dict[str, TickerContext] = {
    "AAPL": TickerContext(
        ticker="AAPL",
        aliases=("apple", "iphone", "mac", "app store"),
        themes=("smartphones", "consumer electronics", "ai devices", "semiconductors"),
        peers=("MSFT", "GOOGL", "META", "NVDA", "QCOM", "AVGO"),
        allow_sector_guessing=True,
    ),
    "MSFT": TickerContext(
        ticker="MSFT",
        aliases=("microsoft", "azure", "office", "windows", "copilot"),
        themes=("cloud", "enterprise software", "ai infrastructure", "gaming"),
        peers=("AAPL", "GOOGL", "AMZN", "ORCL", "CRM", "NVDA"),
        allow_sector_guessing=True,
    ),
    "NVDA": TickerContext(
        ticker="NVDA",
        aliases=("nvidia", "geforce", "cuda", "blackwell", "ai chips"),
        themes=("semiconductors", "ai infrastructure", "data centers", "gpu"),
        peers=("AMD", "AVGO", "QCOM", "INTC", "TSM", "MSFT"),
        allow_sector_guessing=True,
    ),
    "PLTR": TickerContext(
        ticker="PLTR",
        aliases=("palantir", "foundry", "gotham", "aip"),
        themes=("defense software", "government contracts", "enterprise ai", "data analytics"),
        peers=("MSFT", "SNOW", "CRM", "ORCL", "NOW"),
        allow_sector_guessing=True,
    ),
}

DIRECT_RELEVANCE_THRESHOLD = 0.35
SECTOR_RELEVANCE_THRESHOLD = 0.05
EVERGREEN_TERMS = ("history", "headquarters", "profile", "overview", "encyclopedia", "britannica")


def fetch_ticker_news(
    ticker: str,
    *,
    limit: int = 5,
    lookback: timedelta = NEWS_LOOKBACK,
    raise_on_error: bool = False,
) -> list[NewsArticle]:
    key = ticker.upper()
    cache_key = f"{key}:{int(lookback.total_seconds())}"
    now = datetime.now(UTC)
    _prune_expired_cache(now)

    cached = _news_cache.get(cache_key)
    if cached and now - cached[0] < NEWS_CACHE_TTL:
        return cached[1][:limit]

    try:
        articles = _fetch_alphavantage_news(key, lookback=lookback)
    except RateLimitError:
        # Triage should still work without news, but the direct news endpoint can opt into visible errors.
        if raise_on_error:
            raise
        return []
    except MarketDataError as exc:
        # Keep Today resilient; callers that need diagnostics pass raise_on_error=True.
        if raise_on_error:
            if isinstance(exc, NewsProviderConfigError):
                raise NewsUnavailableError(str(exc)) from exc
            raise NewsUnavailableError("News provider is unavailable. Try again later.") from exc
        return []

    _news_cache[cache_key] = (now, articles)
    return articles[:limit]


def _prune_expired_cache(now: datetime) -> None:
    for cache_key, (cached_at, _) in list(_news_cache.items()):
        if now - cached_at >= NEWS_CACHE_TTL:
            _news_cache.pop(cache_key, None)


def classify_news(title: str, summary: str = "") -> tuple[str, int]:
    text = _normalise_news_text(f"{title} {summary}")
    for category, impact, keywords in KEYWORD_RULES:
        # Whole-token matching avoids false positives like "sec" inside "seconds".
        if any(_normalise_news_text(keyword) in text for keyword in keywords):
            return category, impact
    return "general", 0


def _normalise_news_text(value: str) -> str:
    text = "".join(ch if ch.isalnum() else " " for ch in value.lower())
    return f" {' '.join(text.split())} "


def _fetch_alphavantage_news(ticker: str, *, lookback: timedelta) -> list[NewsArticle]:
    api_key = os.getenv("ALPHAVANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise NewsProviderConfigError("Set ALPHAVANTAGE_API_KEY to enable ticker news.")

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
        published_at = _parse_alphavantage_time(str(item.get("time_published", "")))
        if published_at is None or published_at < cutoff:
            continue

        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not title:
            continue

        category, impact = classify_news(title, summary)
        articles.append(_news_article_from_payload(ticker, item, title, summary, published_at, category, impact))

    return articles


def _news_article_from_payload(
    ticker: str,
    item: dict,
    title: str,
    summary: str,
    published_at: datetime,
    category: str,
    impact: int,
) -> NewsArticle:
    relevance = classify_relevance(ticker, item, title, summary)
    return NewsArticle(
        title=title,
        url=str(item.get("url") or ""),
        source=str(item.get("source") or "News"),
        published_at=published_at,
        summary=summary,
        category=category,
        impact=impact,
        relevance_score=relevance["relevance_score"],
        ticker_sentiment_score=relevance["ticker_sentiment_score"],
        ticker_sentiment_label=relevance["ticker_sentiment_label"],
        overall_sentiment_score=_float_or_none(item.get("overall_sentiment_score")),
        overall_sentiment_label=_optional_string(item.get("overall_sentiment_label")),
        relevance_type=str(relevance["relevance_type"]),
        is_scoreable=bool(relevance["is_scoreable"]) and impact > 0,
        score_impact=int(relevance["score_impact"]) if impact > 0 else 0,
        relevance_reason=str(relevance["relevance_reason"]),
    )


def classify_relevance(ticker: str, item: dict, title: str, summary: str = "") -> dict[str, object]:
    key = ticker.upper()
    text = _normalise_news_text(f"{title} {summary} {item.get('source', '')}")
    sentiment = _target_sentiment(item, key)
    relevance_score = _float_or_none(sentiment.get("relevance_score")) if sentiment else None
    ticker_sentiment_score = _float_or_none(sentiment.get("ticker_sentiment_score")) if sentiment else None
    ticker_sentiment_label = _optional_string(sentiment.get("ticker_sentiment_label")) if sentiment else None

    # Evergreen/background content can mention the company but should not create a trading alert.
    if _is_evergreen_news(text):
        return _relevance_result(
            "ignored",
            relevance_score,
            ticker_sentiment_score,
            ticker_sentiment_label,
            "ignored: evergreen or background reference",
        )

    context = get_ticker_context(key)
    headline = _normalise_news_text(title)
    headline_mentions_company = _mentions_direct_ticker(headline, key) or _mentions_alias(headline, context.aliases)
    # Direct relevance comes from the provider's requested-ticker metadata; context only enriches sector matches.
    if sentiment is not None and relevance_score is not None and relevance_score >= DIRECT_RELEVANCE_THRESHOLD:
        return _relevance_result(
            "direct",
            relevance_score,
            ticker_sentiment_score,
            ticker_sentiment_label,
            "direct: target ticker relevance is high",
        )

    if sentiment is not None and headline_mentions_company:
        return _relevance_result(
            "direct",
            relevance_score,
            ticker_sentiment_score,
            ticker_sentiment_label,
            "direct: headline mentions the watched company and provider includes its ticker",
        )

    if not context.allow_sector_guessing:
        # Unknown tickers intentionally do not receive weak sector inference.
        return _relevance_result(
            "ignored",
            relevance_score,
            ticker_sentiment_score,
            ticker_sentiment_label,
            "ignored: no ticker context and no direct ticker relevance",
        )

    if sentiment is not None and relevance_score is not None and relevance_score >= SECTOR_RELEVANCE_THRESHOLD:
        return _relevance_result(
            "sector_context",
            relevance_score,
            ticker_sentiment_score,
            ticker_sentiment_label,
            "display-only: provider associates the ticker, but headline does not establish direct company news",
        )

    if _mentions_peer(item, text, context.peers) or _mentions_alias(text, context.themes):
        return _relevance_result(
            "sector_context",
            relevance_score,
            ticker_sentiment_score,
            ticker_sentiment_label,
            "display-only: related peer or sector theme",
        )

    return _relevance_result(
        "ignored",
        relevance_score,
        ticker_sentiment_score,
        ticker_sentiment_label,
        "ignored: low ticker relevance",
    )


def _relevance_result(
    relevance_type: str,
    relevance_score: float | None,
    ticker_sentiment_score: float | None,
    ticker_sentiment_label: str | None,
    relevance_reason: str,
    *,
    score_impact: int = 0,
) -> dict[str, object]:
    return {
        "relevance_type": relevance_type,
        "relevance_score": relevance_score,
        "ticker_sentiment_score": ticker_sentiment_score,
        "ticker_sentiment_label": ticker_sentiment_label,
        "is_scoreable": relevance_type == "direct" and score_impact > 0,
        "score_impact": score_impact,
        "relevance_reason": relevance_reason,
    }


def get_ticker_context(ticker: str) -> TickerContext:
    key = ticker.upper()
    return TICKER_CONTEXT.get(key, TickerContext(ticker=key))


def _target_sentiment(item: dict, ticker: str) -> dict[str, object] | None:
    for sentiment in item.get("ticker_sentiment", []):
        if str(sentiment.get("ticker", "")).upper() == ticker:
            return sentiment
    return None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _is_evergreen_news(text: str) -> bool:
    return any(_normalise_news_text(term) in text for term in EVERGREEN_TERMS)


def _mentions_direct_ticker(text: str, ticker: str) -> bool:
    return _normalise_news_text(f"${ticker}") in text or _normalise_news_text(ticker) in text


def _mentions_alias(text: str, aliases: tuple[str, ...]) -> bool:
    return any(_normalise_news_text(alias) in text for alias in aliases)


def _mentions_peer(item: dict, text: str, peers: tuple[str, ...]) -> bool:
    mentioned_tickers = {str(sentiment.get("ticker", "")).upper() for sentiment in item.get("ticker_sentiment", [])}
    if mentioned_tickers.intersection(peers):
        return True
    return any(_normalise_news_text(peer) in text or _normalise_news_text(f"${peer}") in text for peer in peers)


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
