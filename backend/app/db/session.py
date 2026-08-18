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
            _ensure_company_metadata_columns()
            _ensure_watchlist_note_columns()
            _ensure_triage_snapshot_columns()
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


def _ensure_company_metadata_columns() -> None:
    if engine is None:
        return

    inspector = inspect(engine)
    if "companies" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("companies")}
    statements = {
        "currency": "ALTER TABLE companies ADD COLUMN currency VARCHAR(12) NOT NULL DEFAULT ''",
        "market_cap": "ALTER TABLE companies ADD COLUMN market_cap BIGINT",
        "pe_ratio": "ALTER TABLE companies ADD COLUMN pe_ratio FLOAT",
        "eps": "ALTER TABLE companies ADD COLUMN eps FLOAT",
        "revenue_ttm": "ALTER TABLE companies ADD COLUMN revenue_ttm BIGINT",
        "revenue_growth_yoy": "ALTER TABLE companies ADD COLUMN revenue_growth_yoy FLOAT",
        "profit_margin": "ALTER TABLE companies ADD COLUMN profit_margin FLOAT",
        "debt_to_equity": "ALTER TABLE companies ADD COLUMN debt_to_equity FLOAT",
        "dividend_yield": "ALTER TABLE companies ADD COLUMN dividend_yield FLOAT",
    }
    with engine.begin() as connection:
        for column, statement in statements.items():
            if column not in existing:
                connection.execute(text(statement))


def _ensure_triage_snapshot_columns() -> None:
    if engine is None:
        return

    # create_all does not alter existing tables, so keep local Docker databases compatible.
    inspector = inspect(engine)
    if "triage_snapshots" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("triage_snapshots")}
    json_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
    json_default = "'[]'::jsonb" if engine.dialect.name == "postgresql" else "'[]'"
    statements = {
        "top_news": f"ALTER TABLE triage_snapshots ADD COLUMN top_news {json_type} NOT NULL DEFAULT {json_default}",
        "price_change_pct": "ALTER TABLE triage_snapshots ADD COLUMN price_change_pct FLOAT NOT NULL DEFAULT 0",
        "as_of_date": "ALTER TABLE triage_snapshots ADD COLUMN as_of_date DATE NOT NULL DEFAULT CURRENT_DATE",
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
