from datetime import UTC, datetime

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.db import models

WatchlistRecord = dict[str, str | datetime | None]

_memory_watchlist: dict[str, WatchlistRecord] = {}


def _now() -> datetime:
    return datetime.now(UTC)


def _normalise_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _clean_note(value: str | None) -> str:
    return (value or "").strip()


def _record(
    ticker: str,
    created_at: datetime,
    *,
    watch_reason: str = "",
    main_risk: str = "",
    change_my_mind: str = "",
    last_check_status: str | None = None,
    last_check_message: str | None = None,
    last_checked_at: datetime | None = None,
) -> WatchlistRecord:
    return {
        "ticker": ticker,
        "created_at": created_at,
        "signal": "Tracked",
        "watch_reason": watch_reason,
        "main_risk": main_risk,
        "change_my_mind": change_my_mind,
        "last_check_status": last_check_status,
        "last_check_message": last_check_message,
        "last_checked_at": last_checked_at,
    }


def _created_at(record: WatchlistRecord | None) -> datetime:
    value = record["created_at"] if record else None
    return value if isinstance(value, datetime) else _now()


def _model_record(item: models.WatchlistItem) -> WatchlistRecord:
    return _record(
        item.ticker,
        item.created_at,
        watch_reason=item.watch_reason,
        main_risk=item.main_risk,
        change_my_mind=item.change_my_mind,
        last_check_status=item.last_check_status,
        last_check_message=item.last_check_message,
        last_checked_at=item.last_checked_at,
    )


def _set_notes(
    item: models.WatchlistItem,
    *,
    watch_reason: str = "",
    main_risk: str = "",
    change_my_mind: str = "",
) -> None:
    item.watch_reason = _clean_note(watch_reason)
    item.main_risk = _clean_note(main_risk)
    item.change_my_mind = _clean_note(change_my_mind)


def list_watchlist(db: Session | None) -> list[WatchlistRecord]:
    if db is None:
        return [item for _, item in sorted(_memory_watchlist.items(), key=lambda entry: entry[1]["created_at"])]

    items = db.query(models.WatchlistItem).order_by(asc(models.WatchlistItem.created_at)).all()
    return [_model_record(item) for item in items]


def add_watchlist_item(
    db: Session | None,
    ticker: str,
    *,
    watch_reason: str = "",
    main_risk: str = "",
    change_my_mind: str = "",
) -> WatchlistRecord:
    normalised = _normalise_ticker(ticker)
    if db is None:
        existing = _memory_watchlist.get(normalised)
        created_at = _created_at(existing)
        _memory_watchlist[normalised] = _record(
            normalised,
            created_at,
            watch_reason=_clean_note(watch_reason),
            main_risk=_clean_note(main_risk),
            change_my_mind=_clean_note(change_my_mind),
            last_check_status=existing.get("last_check_status") if existing else None,
            last_check_message=existing.get("last_check_message") if existing else None,
            last_checked_at=existing.get("last_checked_at") if existing else None,
        )
        return _memory_watchlist[normalised]

    existing = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == normalised).first()
    if existing:
        _set_notes(existing, watch_reason=watch_reason, main_risk=main_risk, change_my_mind=change_my_mind)
        db.commit()
        db.refresh(existing)
        return _model_record(existing)

    item = models.WatchlistItem(ticker=normalised)
    _set_notes(item, watch_reason=watch_reason, main_risk=main_risk, change_my_mind=change_my_mind)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _model_record(item)


def update_watchlist_item(
    db: Session | None,
    ticker: str,
    replacement: str,
    *,
    watch_reason: str = "",
    main_risk: str = "",
    change_my_mind: str = "",
) -> WatchlistRecord:
    current = _normalise_ticker(ticker)
    updated = _normalise_ticker(replacement)
    if db is None:
        source = _memory_watchlist.pop(current, None)
        existing = _memory_watchlist.get(updated)
        status_source = existing or source
        created_at = _created_at(existing or source)
        _memory_watchlist[updated] = _record(
            updated,
            created_at,
            watch_reason=_clean_note(watch_reason),
            main_risk=_clean_note(main_risk),
            change_my_mind=_clean_note(change_my_mind),
            last_check_status=status_source.get("last_check_status") if status_source else None,
            last_check_message=status_source.get("last_check_message") if status_source else None,
            last_checked_at=status_source.get("last_checked_at") if status_source else None,
        )
        return _memory_watchlist[updated]

    item = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == current).first()
    existing = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == updated).first()
    if existing and existing is not item:
        _set_notes(existing, watch_reason=watch_reason, main_risk=main_risk, change_my_mind=change_my_mind)
        if item:
            db.delete(item)
        db.commit()
        db.refresh(existing)
        return _model_record(existing)

    if item is None:
        return add_watchlist_item(db, updated, watch_reason=watch_reason, main_risk=main_risk, change_my_mind=change_my_mind)

    item.ticker = updated
    _set_notes(item, watch_reason=watch_reason, main_risk=main_risk, change_my_mind=change_my_mind)
    db.commit()
    db.refresh(item)
    return _model_record(item)


def remove_watchlist_item(db: Session | None, ticker: str) -> None:
    normalised = _normalise_ticker(ticker)
    if db is None:
        _memory_watchlist.pop(normalised, None)
        return

    item = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == normalised).first()
    if item:
        db.delete(item)
        db.commit()


def update_check_status(
    db: Session | None,
    ticker: str,
    status: str,
    *,
    message: str | None = None,
    checked_at: datetime | None = None,
) -> None:
    normalised = _normalise_ticker(ticker)
    checked_at = checked_at or _now()
    if db is None:
        existing = _memory_watchlist.get(normalised)
        if existing is None:
            return
        existing["last_check_status"] = status
        existing["last_check_message"] = message
        existing["last_checked_at"] = checked_at
        return

    item = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == normalised).first()
    if item is None:
        return
    item.last_check_status = status
    item.last_check_message = message
    item.last_checked_at = checked_at
