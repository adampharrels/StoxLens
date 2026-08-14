from datetime import UTC, datetime
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
from app.services.watchlist import list_watchlist

_memory_triage_snapshots: dict[str, list[dict[str, object]]] = {}


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


def _snapshot_value(snapshot: models.TriageSnapshot | dict[str, object], key: str) -> object:
    return getattr(snapshot, key) if isinstance(snapshot, models.TriageSnapshot) else snapshot.get(key)


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
    previous_created_at = _snapshot_value(previous, "created_at")
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
        previous_created_at=previous_created_at if isinstance(previous_created_at, datetime) else None,
        score_delta=score_delta,
        severity_changed=previous_severity != item.severity,
        new_reasons=new_reasons,
        removed_reasons=removed_reasons,
        details=details,
    )


def _save_snapshot(db: Session | None, item: TriageItemOut) -> None:
    payload = {
        "ticker": item.ticker,
        "attention_score": item.attention_score,
        "severity": item.severity,
        "top_reasons": [_reason_payload(reason) for reason in item.reasons[:3]],
        "price": item.price,
        "volume": float(item.metrics.get("volume", 0.0)),
        "rsi": float(item.metrics.get("rsi", 0.0)),
        "moving_average_status": str(item.metrics.get("ma_signal", "")),
        "created_at": datetime.now(UTC),
    }
    if db is None:
        _memory_triage_snapshots.setdefault(item.ticker, []).append(payload)
        _memory_triage_snapshots[item.ticker] = _memory_triage_snapshots[item.ticker][-20:]
        return

    db.add(models.TriageSnapshot(**payload))
    db.commit()


def build_triage(db: Session | None, tickers: str | None = None) -> TriageResponse:
    watch_items = [] if tickers else _watchlist_items(db)
    watch_notes = {str(item["ticker"]): item for item in watch_items}
    ticker_list = [item.strip().upper() for item in tickers.split(",") if item.strip()] if tickers else list(watch_notes)
    ticker_list = list(dict.fromkeys(ticker_list))[:12]

    items: list[TriageItemOut] = []
    for ticker in ticker_list:
        try:
            df = clean_price_data(fetch_price_data(ticker))
        except (TickerNotFoundError, InsufficientPriceDataError, RateLimitError, MarketDataError):
            continue
        item = score_ticker(ticker, df, fetch_ticker_news(ticker), watch_notes.get(ticker))
        previous = _latest_snapshot(db, ticker)
        item.changes = _snapshot_changes(previous, item)
        _save_snapshot(db, item)
        items.append(item)

    items.sort(key=lambda item: (item.attention_score, abs(item.price_change_pct)), reverse=True)
    return TriageResponse(generated_at=datetime.now(UTC), items=items)
