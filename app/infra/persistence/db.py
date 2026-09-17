"""Database engine and session management for SQLite + SQLAlchemy."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


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
    elif database_url.startswith("sqlite"):
        # A pooled (reused) connection can, in practice, serve a read against a
        # transaction snapshot predating another connection's very recent
        # commit (observed directly: polling `conversations.objective_met`
        # right after an external write raced stale intermittently under
        # request load, even with explicit BEGIN — see below). NullPool opens
        # a fresh connection per checkout/close cycle, which removes that
        # class of bug outright; cost is negligible for SQLite at this scale.
        poolclass = NullPool
    _engine = create_engine(
        database_url, future=True, connect_args=connect_args, poolclass=poolclass
    )

    if database_url.startswith("sqlite"):
        # pysqlite's own implicit-transaction tracking only opens a transaction
        # before DML, not SELECT — it disagrees with SQLAlchemy's "autobegin",
        # which can make a freshly-checked-out pooled connection serve a SELECT
        # against a transaction snapshot from *before* another connection's
        # commit (observed: reading `conversations.objective_met` right after
        # an external write raced ~50% stale). Disabling pysqlite's own
        # transaction handling and letting SQLAlchemy issue BEGIN explicitly is
        # the standard fix (see SQLAlchemy's pysqlite transactional-DDL docs).
        @event.listens_for(_engine, "connect")
        def _sqlite_disable_pysqlite_txn(dbapi_connection, _connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(_engine, "begin")
        def _sqlite_explicit_begin(conn):
            conn.exec_driver_sql("BEGIN")

    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    # Inline migrations: add new columns to existing prompts tables.
    for migration_sql in [
        "ALTER TABLE prompts ADD COLUMN model VARCHAR(128)",
        "ALTER TABLE prompts ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
    ]:
        try:
            with _engine.connect() as conn:
                conn.execute(text(migration_sql))
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

