"""Database engine and session management for SQLite + SQLAlchemy."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for ORM models."""


_engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None


def init_engine(database_url: str) -> None:
    """Initialise global engine and session factory."""
    global _engine, SessionLocal
    if _engine is not None:
        return

    # Ensure SQLite directory exists (e.g. ./data).
    if database_url.startswith("sqlite:///./"):
        path = database_url.replace("sqlite:///./", "", 1)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    connect_args = {}
    poolclass = None
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if ":memory:" in database_url:
        poolclass = StaticPool
    _engine = create_engine(
        database_url, future=True, connect_args=connect_args, poolclass=poolclass
    )
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    # Inline migration: add is_active column to existing prompts tables.
    try:
        with _engine.connect() as conn:
            conn.execute(text("ALTER TABLE prompts ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
            conn.commit()
    except Exception:
        pass  # column already exists or table doesn't exist yet (create_all will add it)


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Yield a DB session for use in FastAPI dependencies."""
    if SessionLocal is None:
        raise RuntimeError("Session factory not initialised. Call init_engine() first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

