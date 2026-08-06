from datetime import UTC, datetime

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.db import models

_memory_watchlist: dict[str, datetime] = {}


def _now() -> datetime:
    return datetime.now(UTC)


def _normalise_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def list_watchlist(db: Session | None) -> list[dict[str, str | datetime]]:
    if db is None:
        return [
            {"ticker": ticker, "created_at": created_at, "signal": "Tracked"}
            for ticker, created_at in sorted(_memory_watchlist.items(), key=lambda item: item[1])
        ]

    items = db.query(models.WatchlistItem).order_by(asc(models.WatchlistItem.created_at)).all()
    return [{"ticker": item.ticker, "created_at": item.created_at, "signal": "Tracked"} for item in items]


def add_watchlist_item(db: Session | None, ticker: str) -> dict[str, str | datetime]:
    normalised = _normalise_ticker(ticker)
    if db is None:
        _memory_watchlist.setdefault(normalised, _now())
        return {"ticker": normalised, "created_at": _memory_watchlist[normalised], "signal": "Tracked"}

    existing = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == normalised).first()
    if existing:
        return {"ticker": existing.ticker, "created_at": existing.created_at, "signal": "Tracked"}

    item = models.WatchlistItem(ticker=normalised)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"ticker": item.ticker, "created_at": item.created_at, "signal": "Tracked"}


def update_watchlist_item(db: Session | None, ticker: str, replacement: str) -> dict[str, str | datetime]:
    current = _normalise_ticker(ticker)
    updated = _normalise_ticker(replacement)
    if db is None:
        created_at = _memory_watchlist.pop(current, _now())
        _memory_watchlist[updated] = created_at
        return {"ticker": updated, "created_at": created_at, "signal": "Tracked"}

    item = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == current).first()
    existing = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == updated).first()
    if existing and existing is not item:
        if item:
            db.delete(item)
            db.commit()
        return {"ticker": existing.ticker, "created_at": existing.created_at, "signal": "Tracked"}

    if item is None:
        return add_watchlist_item(db, updated)

    item.ticker = updated
    db.commit()
    db.refresh(item)
    return {"ticker": item.ticker, "created_at": item.created_at, "signal": "Tracked"}


def remove_watchlist_item(db: Session | None, ticker: str) -> None:
    normalised = _normalise_ticker(ticker)
    if db is None:
        _memory_watchlist.pop(normalised, None)
        return

    item = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == normalised).first()
    if item:
        db.delete(item)
        db.commit()
