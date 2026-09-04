from datetime import UTC, date, datetime
from math import sqrt

import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.triage import NewsArticleOut, TriageChangeOut, TriageItemOut, TriageReasonOut, TriageResponse, WatchNoteOut
from app.services.market_data import (
    InsufficientPriceDataError,
    MarketDataError,
    RateLimitError,
    TickerNotFoundError,
    assess_data_quality,
    clean_price_data,
    fetch_price_data,
)
from app.services.news import NewsArticle, fetch_ticker_news
from app.services.signals import calculate_signals
from app.services.watchlist import list_watchlist, update_check_status

_memory_triage_snapshots: dict[str, list[dict[str, object]]] = {}
TRIAGE_SNAPSHOT_RETENTION = 20


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _percentile(series: pd.Series, value: float) -> float:
    clean = series.dropna()
    if clean.empty:
        return 0.0
    return float((clean <= value).mean())


def _reason(code: str, label: str, detail: str, impact: int) -> TriageReasonOut:
    return TriageReasonOut(code=code, label=label, detail=detail, impact=impact)


def _reason_payload(reason: TriageReasonOut) -> dict[str, str | int]:
    return {"code": reason.code, "label": reason.label, "detail": reason.detail, "impact": reason.impact}


def _news_payload(article: NewsArticleOut) -> dict[str, str | int]:
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "category": article.category,
        "impact": article.impact,
    }


def _news_to_schema(article: NewsArticle) -> NewsArticleOut:
    return NewsArticleOut(
        title=article.title,
        url=article.url,
        source=article.source,
        published_at=article.published_at,
        category=article.category,
        impact=article.impact,
    )


def _watch_note(ticker: str, item: dict[str, object] | None = None) -> WatchNoteOut:
    return WatchNoteOut(
        ticker=ticker.upper(),
        watch_reason=str(item.get("watch_reason", "")) if item else "",
        main_risk=str(item.get("main_risk", "")) if item else "",
        change_my_mind=str(item.get("change_my_mind", "")) if item else "",
    )


def _issue_item(
    ticker: str,
    status: str,
    message: str,
    watch_note: dict[str, object] | None = None,
    *,
    checked_at: datetime | None = None,
) -> TriageItemOut:
    return TriageItemOut(
        ticker=ticker.upper(),
        status=status,  # type: ignore[arg-type]
        issue_message=message,
        last_checked_at=checked_at,
        watch_note=_watch_note(ticker, watch_note),
    )


def _provider_issue_message(exc: Exception) -> str:
    if isinstance(exc, InsufficientPriceDataError):
        return "Provider could not return enough price history."
    if isinstance(exc, RateLimitError):
        return "Market data provider rate limit was reached."
    if isinstance(exc, TickerNotFoundError):
        return "Ticker could not be found or is not supported."
    return "Unable to check this ticker right now."


def score_ticker(
    ticker: str,
    df: pd.DataFrame,
    news: list[NewsArticle] | None = None,
    watch_note: dict[str, object] | None = None,
) -> TriageItemOut:
    signals = calculate_signals(df)
    quality = assess_data_quality(df)
    signals["data_quality_score"] = int(quality["score"])

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)
    daily_returns = close.pct_change()
    current = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else current
    price_change_pct = float((current / previous) - 1) if previous else 0.0

    ma_50 = close.rolling(50, min_periods=20).mean()
    ma_200 = close.rolling(200, min_periods=100).mean()
    ma_50_current = float(ma_50.iloc[-1]) if pd.notna(ma_50.iloc[-1]) else current
    ma_200_current = float(ma_200.iloc[-1]) if pd.notna(ma_200.iloc[-1]) else current
    ma_50_previous = float(ma_50.iloc[-2]) if len(ma_50) > 1 and pd.notna(ma_50.iloc[-2]) else ma_50_current
    ma_200_previous = float(ma_200.iloc[-2]) if len(ma_200) > 1 and pd.notna(ma_200.iloc[-2]) else ma_200_current

    rolling_vol = daily_returns.rolling(30, min_periods=20).std() * sqrt(252)
    vol_current = float(rolling_vol.iloc[-1]) if pd.notna(rolling_vol.iloc[-1]) else float(signals["volatility_30d"])
    vol_percentile = _percentile(rolling_vol.tail(252), vol_current)

    abs_return = abs(price_change_pct)
    normal_move = float(daily_returns.tail(60).std() * 1.5) if len(daily_returns.dropna()) >= 20 else 0.0
    volume_90 = float(volume.rolling(90, min_periods=20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean())
    latest_volume = float(volume.iloc[-1])
    volume_ratio = latest_volume / volume_90 if volume_90 else 1.0

    reasons: list[TriageReasonOut] = []

    if previous >= ma_50_previous and current < ma_50_current:
        reasons.append(_reason("below_50d", "50D break", "Price crossed below the 50-day moving average.", 3))
    elif previous <= ma_50_previous and current > ma_50_current:
        reasons.append(_reason("above_50d", "50D recovery", "Price crossed back above the 50-day moving average.", 2))

    if previous >= ma_200_previous and current < ma_200_current:
        reasons.append(_reason("below_200d", "200D break", "Price crossed below long-term trend support.", 4))
    elif previous <= ma_200_previous and current > ma_200_current:
        reasons.append(_reason("above_200d", "200D recovery", "Price reclaimed long-term trend support.", 3))

    rsi = float(signals["rsi"])
    if rsi >= 75:
        reasons.append(_reason("rsi_overbought", "RSI overbought", f"RSI is elevated at {rsi:.1f}.", 2))
    elif rsi <= 30:
        reasons.append(_reason("rsi_oversold", "RSI oversold", f"RSI is compressed at {rsi:.1f}.", 3))

    if vol_percentile >= 0.9:
        reasons.append(_reason("vol_spike", "Volatility spike", f"30-day volatility is in the {_pct(vol_percentile)} percentile.", 3))

    if float(signals["max_drawdown"]) <= -0.2:
        reasons.append(_reason("drawdown", "Large drawdown", f"Drawdown is {_pct(float(signals['max_drawdown']))}.", 3))

    if volume_ratio >= 1.5:
        reasons.append(_reason("volume_surge", "Volume surge", f"Latest volume is {volume_ratio:.1f}x the 90-day average.", 2))

    if normal_move > 0 and abs_return >= normal_move:
        reasons.append(_reason("abnormal_move", "Abnormal daily move", f"Latest move of {_pct(price_change_pct)} is larger than normal.", 2))

    if int(signals["data_quality_score"]) < 4:
        reasons.append(_reason("data_quality", "Data quality", "Market data quality is below the preferred threshold.", 2))

    news_items = news or []
    news_impact = min(4, sum(article.impact for article in news_items[:3]))
    if news_impact > 0:
        categories = ", ".join(dict.fromkeys(article.category for article in news_items[:3]))
        reasons.append(_reason("news", "Price-relevant news", f"Recent {categories} news should be reviewed.", news_impact))

    score = min(100, sum(reason.impact for reason in reasons) * 12)
    severity = "High" if score >= 60 else "Medium" if score >= 30 else "Low"

    metrics: dict[str, float | int | str] = {
        "return_1m": float(signals["return_1m"]),
        "return_3m": float(signals["return_3m"]),
        "volatility_30d": float(signals["volatility_30d"]),
        "volatility_percentile": vol_percentile,
        "max_drawdown": float(signals["max_drawdown"]),
        "rsi": rsi,
        "volume": latest_volume,
        "volume_ratio": volume_ratio,
        "ma_signal": str(signals["ma_signal"]),
        "data_quality_score": int(signals["data_quality_score"]),
    }

    return TriageItemOut(
        ticker=ticker.upper(),
        status="ok",
        attention_score=score,
        severity=severity,
        price=current,
        price_change_pct=price_change_pct,
        as_of_date=df.index[-1].date(),
        reasons=reasons,
        news=[_news_to_schema(article) for article in news_items],
        metrics=metrics,
        watch_note=_watch_note(ticker, watch_note),
    )


def _watchlist_items(db: Session | None) -> list[dict[str, object]]:
    return [dict(item) for item in list_watchlist(db)]


def _snapshot_reasons(snapshot: models.TriageSnapshot | dict[str, object]) -> list[dict[str, object]]:
    value = snapshot.top_reasons if isinstance(snapshot, models.TriageSnapshot) else snapshot.get("top_reasons", [])
    return value if isinstance(value, list) else []


def _snapshot_news(snapshot: models.TriageSnapshot | dict[str, object]) -> list[dict[str, object]]:
    value = snapshot.top_news if isinstance(snapshot, models.TriageSnapshot) else snapshot.get("top_news", [])
    return value if isinstance(value, list) else []


def _snapshot_value(snapshot: models.TriageSnapshot | dict[str, object], key: str) -> object:
    return getattr(snapshot, key) if isinstance(snapshot, models.TriageSnapshot) else snapshot.get(key)


def _snapshot_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _snapshot_date(value: object, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def _latest_snapshot(db: Session | None, ticker: str) -> models.TriageSnapshot | dict[str, object] | None:
    key = ticker.upper()
    if db is None:
        snapshots = _memory_triage_snapshots.get(key, [])
        return snapshots[-1] if snapshots else None

    return (
        db.query(models.TriageSnapshot)
        .filter(models.TriageSnapshot.ticker == key)
        .order_by(desc(models.TriageSnapshot.created_at), desc(models.TriageSnapshot.id))
        .first()
    )


def _latest_snapshots(db: Session | None, ticker: str, limit: int = 2) -> list[models.TriageSnapshot | dict[str, object]]:
    key = ticker.upper()
    if db is None:
        snapshots = _memory_triage_snapshots.get(key, [])
        return snapshots[-limit:][::-1]

    return (
        db.query(models.TriageSnapshot)
        .filter(models.TriageSnapshot.ticker == key)
        .order_by(desc(models.TriageSnapshot.created_at), desc(models.TriageSnapshot.id))
        .limit(limit)
        .all()
    )


def _ma_label(value: object) -> str:
    labels = {
        "above_both": "above 50D and 200D",
        "above_50_only": "above 50D, below 200D",
        "below_both": "below 50D and 200D",
    }
    return labels.get(str(value), str(value))


def _snapshot_changes(previous: models.TriageSnapshot | dict[str, object] | None, item: TriageItemOut) -> TriageChangeOut | None:
    if previous is None:
        return None

    previous_score = int(_snapshot_value(previous, "attention_score") or 0)
    previous_severity = str(_snapshot_value(previous, "severity") or "Low")
    previous_created_at = _snapshot_datetime(_snapshot_value(previous, "created_at"))
    previous_reason_codes = {str(reason.get("code")) for reason in _snapshot_reasons(previous) if isinstance(reason, dict)}
    current_reason_codes = {reason.code for reason in item.reasons}
    current_reason_map = {reason.code: reason for reason in item.reasons}

    new_codes = current_reason_codes - previous_reason_codes
    removed_codes = previous_reason_codes - current_reason_codes
    new_reasons = [current_reason_map[code].label for code in new_codes if code in current_reason_map]
    removed_reasons = [
        str(reason.get("label"))
        for reason in _snapshot_reasons(previous)
        if isinstance(reason, dict) and str(reason.get("code")) in removed_codes
    ]

    details: list[str] = []
    if previous_severity != item.severity:
        details.append(f"Attention changed from {previous_severity} to {item.severity}.")

    for code in new_codes:
        reason = current_reason_map.get(code)
        if reason:
            details.append(reason.detail)

    previous_ma = _snapshot_value(previous, "moving_average_status")
    current_ma = item.metrics.get("ma_signal")
    if previous_ma and current_ma and str(previous_ma) != str(current_ma):
        details.append(f"Moving average status changed from {_ma_label(previous_ma)} to {_ma_label(current_ma)}.")

    score_delta = item.attention_score - previous_score
    if score_delta > 0:
        details.append(f"Attention score increased from {previous_score} to {item.attention_score}.")
    elif score_delta < 0:
        details.append(f"Attention score decreased from {previous_score} to {item.attention_score}.")

    if not details:
        details.append("No material change from the previous saved check.")

    return TriageChangeOut(
        previous_attention_score=previous_score,
        previous_severity=previous_severity,  # type: ignore[arg-type]
        previous_created_at=previous_created_at,
        score_delta=score_delta,
        severity_changed=previous_severity != item.severity,
        new_reasons=new_reasons,
        removed_reasons=removed_reasons,
        details=details,
    )


def _snapshot_payload(item: TriageItemOut) -> dict[str, object]:
    return {
        "ticker": item.ticker,
        "attention_score": item.attention_score,
        "severity": item.severity,
        "top_reasons": [_reason_payload(reason) for reason in item.reasons[:3]],
        "top_news": [_news_payload(article) for article in item.news[:3]],
        "price": item.price,
        "price_change_pct": item.price_change_pct,
        "as_of_date": item.as_of_date,
        "volume": float(item.metrics.get("volume", 0.0)),
        "volatility_percentile": float(item.metrics.get("volatility_percentile", 0.0)),
        "volume_ratio": float(item.metrics.get("volume_ratio", 1.0)),
        "rsi": float(item.metrics.get("rsi", 0.0)),
        "moving_average_status": str(item.metrics.get("ma_signal", "")),
        "created_at": datetime.now(UTC),
    }


def _save_snapshot(db: Session | None, item: TriageItemOut) -> models.TriageSnapshot | None:
    payload = _snapshot_payload(item)
    if db is None:
        _memory_triage_snapshots.setdefault(item.ticker, []).append(payload)
        _memory_triage_snapshots[item.ticker] = _memory_triage_snapshots[item.ticker][-TRIAGE_SNAPSHOT_RETENTION:]
        return None

    snapshot = models.TriageSnapshot(**payload)
    db.add(snapshot)
    return snapshot


def _prune_snapshot_history(db: Session, tickers: list[str]) -> None:
    for ticker in tickers:
        stale_ids = [
            snapshot_id
            for (snapshot_id,) in (
                db.query(models.TriageSnapshot.id)
                .filter(models.TriageSnapshot.ticker == ticker)
                .order_by(desc(models.TriageSnapshot.created_at), desc(models.TriageSnapshot.id))
                .offset(TRIAGE_SNAPSHOT_RETENTION)
                .all()
            )
        ]
        if stale_ids:
            db.query(models.TriageSnapshot).filter(models.TriageSnapshot.id.in_(stale_ids)).delete(synchronize_session=False)


def _commit_snapshots(db: Session | None, tickers: list[str]) -> None:
    if db is None:
        return
    _prune_snapshot_history(db, tickers)
    db.commit()


def _ticker_list(db: Session | None, tickers: str | None) -> tuple[list[str], dict[str, dict[str, object]]]:
    watch_items = [] if tickers else _watchlist_items(db)
    watch_notes = {str(item["ticker"]): item for item in watch_items}
    ticker_list = [item.strip().upper() for item in tickers.split(",") if item.strip()] if tickers else list(watch_notes)
    return list(dict.fromkeys(ticker_list))[:12], watch_notes


def _snapshot_item(
    snapshot: models.TriageSnapshot | dict[str, object],
    watch_note: dict[str, object] | None,
) -> TriageItemOut:
    ticker = str(_snapshot_value(snapshot, "ticker"))
    generated_at = _snapshot_datetime(_snapshot_value(snapshot, "created_at")) or datetime.now(UTC)
    reasons = [
        TriageReasonOut(
            code=str(reason.get("code", "")),
            label=str(reason.get("label", "")),
            detail=str(reason.get("detail", "")),
            impact=int(reason.get("impact", 1)),
        )
        for reason in _snapshot_reasons(snapshot)
        if isinstance(reason, dict)
    ]
    news: list[NewsArticleOut] = []
    for article in _snapshot_news(snapshot):
        if not isinstance(article, dict):
            continue
        published_at = _snapshot_datetime(article.get("published_at"))
        if published_at is None:
            continue
        news.append(
            NewsArticleOut(
                title=str(article.get("title", "")),
                url=str(article.get("url", "")),
                source=str(article.get("source", "News")),
                published_at=published_at,
                category=str(article.get("category", "")),
                impact=int(article.get("impact", 1)),
            )
        )

    return TriageItemOut(
        ticker=ticker,
        attention_score=int(_snapshot_value(snapshot, "attention_score") or 0),
        severity=str(_snapshot_value(snapshot, "severity") or "Low"),  # type: ignore[arg-type]
        price=float(_snapshot_value(snapshot, "price") or 0.0),
        price_change_pct=float(_snapshot_value(snapshot, "price_change_pct") or 0.0),
        as_of_date=_snapshot_date(_snapshot_value(snapshot, "as_of_date"), generated_at.date()),
        reasons=reasons,
        news=news,
        metrics={
            "volume": float(_snapshot_value(snapshot, "volume") or 0.0),
            "volatility_percentile": float(_snapshot_value(snapshot, "volatility_percentile") or 0.0),
            "volume_ratio": float(_snapshot_value(snapshot, "volume_ratio") or 1.0),
            "rsi": float(_snapshot_value(snapshot, "rsi") or 0.0),
            "ma_signal": str(_snapshot_value(snapshot, "moving_average_status") or ""),
        },
        watch_note=_watch_note(ticker, watch_note),
        last_checked_at=generated_at,
    )


def read_triage(db: Session | None, tickers: str | None = None) -> TriageResponse:
    ticker_list, watch_notes = _ticker_list(db, tickers)

    items: list[TriageItemOut] = []
    generated_at: datetime | None = None
    for ticker in ticker_list:
        snapshots = _latest_snapshots(db, ticker, limit=2)
        watch_note = watch_notes.get(ticker)
        watch_status = str(watch_note.get("last_check_status", "")) if watch_note else ""
        watch_message = str(watch_note.get("last_check_message", "")) if watch_note else ""
        watch_checked_at = _snapshot_datetime(watch_note.get("last_checked_at")) if watch_note else None
        if not snapshots:
            if watch_status == "data_issue":
                items.append(
                    _issue_item(
                        ticker,
                        "data_issue",
                        watch_message or "Unable to check this ticker right now.",
                        watch_note,
                        checked_at=watch_checked_at,
                    )
                )
            else:
                items.append(_issue_item(ticker, "not_checked", "Run Check to create the first snapshot.", watch_note))
            continue
        snapshot_created_at = _snapshot_datetime(_snapshot_value(snapshots[0], "created_at"))
        if watch_status == "data_issue" and watch_checked_at and (snapshot_created_at is None or watch_checked_at > snapshot_created_at):
            items.append(
                _issue_item(
                    ticker,
                    "data_issue",
                    watch_message or "Unable to check this ticker right now.",
                    watch_note,
                    checked_at=watch_checked_at,
                )
            )
            if generated_at is None or watch_checked_at > generated_at:
                generated_at = watch_checked_at
            continue
        item = _snapshot_item(snapshots[0], watch_note)
        item.changes = _snapshot_changes(snapshots[1] if len(snapshots) > 1 else None, item)
        if snapshot_created_at is not None and (generated_at is None or snapshot_created_at > generated_at):
            generated_at = snapshot_created_at
        items.append(item)

    items.sort(key=lambda item: (item.status == "ok", item.attention_score or -1, abs(item.price_change_pct or 0.0)), reverse=True)
    return TriageResponse(generated_at=generated_at or datetime.now(UTC), items=items)


def build_triage(db: Session | None, tickers: str | None = None) -> TriageResponse:
    ticker_list, watch_notes = _ticker_list(db, tickers)

    items: list[TriageItemOut] = []
    saved_tickers: list[str] = []
    for ticker in ticker_list:
        checked_at = datetime.now(UTC)
        try:
            df = clean_price_data(fetch_price_data(ticker))
        except (TickerNotFoundError, InsufficientPriceDataError, RateLimitError, MarketDataError) as exc:
            message = _provider_issue_message(exc)
            update_check_status(db, ticker, "data_issue", message=message, checked_at=checked_at)
            items.append(_issue_item(ticker, "data_issue", message, watch_notes.get(ticker), checked_at=checked_at))
            continue
        previous = _latest_snapshot(db, ticker)
        news = fetch_ticker_news(ticker)
        item = score_ticker(ticker, df, news, watch_notes.get(ticker))
        item.changes = _snapshot_changes(previous, item)
        item.last_checked_at = checked_at
        _save_snapshot(db, item)
        update_check_status(db, ticker, "ok", checked_at=checked_at)
        saved_tickers.append(ticker)
        items.append(item)

    _commit_snapshots(db, saved_tickers)
    items.sort(key=lambda item: (item.status == "ok", item.attention_score or -1, abs(item.price_change_pct or 0.0)), reverse=True)
    return TriageResponse(generated_at=datetime.now(UTC), items=items)
