import os
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
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
        except SQLAlchemyError as exc:
            print(f"Database unavailable; using in-memory report storage. Reason: {exc}")
            engine.dispose()
            engine = None
            SessionLocal = None


def get_db() -> Generator[Session | None, None, None]:
    if SessionLocal is None:
        yield None
        return
    db: Any = SessionLocal()
    try:
        yield db
    finally:
        db.close()
