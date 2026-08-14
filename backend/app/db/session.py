import os
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL) if DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def init_db() -> None:
    global SessionLocal, engine
    if engine:
        try:
            Base.metadata.create_all(bind=engine)
            _ensure_watchlist_note_columns()
        except SQLAlchemyError as exc:
            print(f"Database unavailable; using in-memory report storage. Reason: {exc}")
            engine.dispose()
            engine = None
            SessionLocal = None


def _ensure_watchlist_note_columns() -> None:
    if engine is None:
        return

    inspector = inspect(engine)
    if "watchlist_items" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("watchlist_items")}
    statements = {
        "watch_reason": "ALTER TABLE watchlist_items ADD COLUMN watch_reason TEXT NOT NULL DEFAULT ''",
        "main_risk": "ALTER TABLE watchlist_items ADD COLUMN main_risk TEXT NOT NULL DEFAULT ''",
        "change_my_mind": "ALTER TABLE watchlist_items ADD COLUMN change_my_mind TEXT NOT NULL DEFAULT ''",
    }
    with engine.begin() as connection:
        for column, statement in statements.items():
            if column not in existing:
                connection.execute(text(statement))


def get_db() -> Generator[Session | None, None, None]:
    if SessionLocal is None:
        yield None
        return
    db: Any = SessionLocal()
    try:
        yield db
    finally:
        db.close()
