from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query

from app.schemas.triage import NewsArticleOut
from app.services.market_data import RateLimitError
from app.services.news import NewsUnavailableError, fetch_ticker_news

router = APIRouter()


@router.get("/{ticker}", response_model=list[NewsArticleOut])
def get_ticker_news(
    ticker: str,
    limit: int = Query(default=5, ge=1, le=20),
    lookback_hours: int = Query(default=168, ge=1, le=168),
) -> list[NewsArticleOut]:
    try:
        articles = fetch_ticker_news(ticker, limit=limit, lookback=timedelta(hours=lookback_hours), raise_on_error=True)
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail="News provider rate limit reached. Try again later.") from exc
    except NewsUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        NewsArticleOut(
            title=article.title,
            url=article.url,
            source=article.source,
            published_at=article.published_at,
            category=article.category,
            impact=article.impact,
        )
        for article in articles
    ]
