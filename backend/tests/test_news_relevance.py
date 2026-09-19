from datetime import UTC, datetime

import pytest

from app.services.news import NewsArticle, classify_relevance
from app.services.triage import _score_news_articles


def test_relevance_uses_requested_ticker_not_first_or_highest() -> None:
    result = classify_relevance("MSFT", {"ticker_sentiment": [
        {"ticker": "NVDA", "relevance_score": "0.99", "ticker_sentiment_score": "0.9"},
        {"ticker": "MSFT", "relevance_score": "0.63", "ticker_sentiment_score": "0.12"},
    ]}, "Microsoft raises guidance")
    assert result["relevance_type"] == "direct"
    assert result["relevance_score"] == 0.63
    assert result["ticker_sentiment_score"] == 0.12


@pytest.mark.parametrize("title", [
    "HP announces new AI PCs",
    "Nvidia acquires Hugging Face",
    "Citigroup adjusts price target on Akamai",
])
def test_high_provider_association_is_direct_but_scores_weakly_without_sentiment(title: str) -> None:
    result = classify_relevance("MSFT", {"ticker_sentiment": [
        {"ticker": "MSFT", "relevance_score": "0.63"},
    ]}, title, "Microsoft is also active in this market.")
    article = NewsArticle(
        title=title, url="https://example.com/news", source="Test",
        published_at=datetime.now(UTC), summary="", category="earnings", impact=4,
        relevance_type=str(result["relevance_type"]), relevance_score=result["relevance_score"],  # type: ignore[arg-type]
        ticker_sentiment_score=result["ticker_sentiment_score"],  # type: ignore[arg-type]
        ticker_sentiment_label=result["ticker_sentiment_label"],  # type: ignore[arg-type]
        relevance_reason=str(result["relevance_reason"]),
    )
    scored = _score_news_articles([article], sector_confirmed=False)[0]

    assert result["relevance_type"] == "direct"
    assert result["score_impact"] == 0
    assert scored.score_impact == 12


def test_missing_target_entry_cannot_borrow_peer_sentiment() -> None:
    result = classify_relevance("MSFT", {"ticker_sentiment": [
        {"ticker": "NVDA", "relevance_score": "0.99", "ticker_sentiment_score": "0.9"},
    ]}, "Nvidia announces partnership with Microsoft")
    assert result["relevance_type"] == "sector_context"
    assert result["relevance_score"] is None
    assert result["ticker_sentiment_score"] is None


@pytest.mark.parametrize("category,impact,expected", [
    ("analyst", 2, 12), ("management", 2, 12), ("earnings", 4, 12), ("general", 0, 0),
])
def test_neutral_direct_news_requires_material_category_for_large_contribution(
    category: str, impact: int, expected: int,
) -> None:
    article = NewsArticle(
        title="Microsoft news", url="https://example.com/news", source="Test",
        published_at=datetime.now(UTC), summary="", category=category, impact=impact,
        relevance_type="direct", relevance_score=0.63,
        ticker_sentiment_score=0.12, ticker_sentiment_label="Neutral",
    )
    scored = _score_news_articles([article], sector_confirmed=False)[0]
    assert scored.score_impact == expected
    assert scored.is_scoreable == (expected > 0)


def test_direct_high_relevance_neutral_general_news_scores_zero() -> None:
    article = NewsArticle(
        title="Microsoft mentioned in market wrap", url="https://example.com/news", source="Test",
        published_at=datetime.now(UTC), summary="", category="general", impact=0,
        relevance_type="direct", relevance_score=0.8,
        ticker_sentiment_score=0.02, ticker_sentiment_label="Neutral",
    )

    scored = _score_news_articles([article], sector_confirmed=False)[0]

    assert scored.score_impact == 0
    assert scored.is_scoreable is False


def test_direct_low_relevance_news_is_capped_at_twelve_points() -> None:
    article = NewsArticle(
        title="Microsoft raises guidance", url="https://example.com/news", source="Test",
        published_at=datetime.now(UTC), summary="", category="guidance", impact=4,
        relevance_type="direct", relevance_score=0.42,
        ticker_sentiment_score=0.4, ticker_sentiment_label="Bullish",
    )

    scored = _score_news_articles([article], sector_confirmed=False)[0]

    assert scored.score_impact == 12


def test_direct_strong_material_news_scores_full_category_cap() -> None:
    article = NewsArticle(
        title="Microsoft raises guidance", url="https://example.com/news", source="Test",
        published_at=datetime.now(UTC), summary="", category="guidance", impact=4,
        relevance_type="direct", relevance_score=0.8,
        ticker_sentiment_score=0.4, ticker_sentiment_label="Bullish",
    )

    scored = _score_news_articles([article], sector_confirmed=False)[0]

    assert scored.score_impact == 36
