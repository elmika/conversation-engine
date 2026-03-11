"""Lightweight startup migrations for SQLite (no Alembic)."""

import logging

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


def run_migrations(engine: Engine) -> None:
    """Apply any schema changes that create_all() cannot handle (e.g. new columns)."""
    with engine.connect() as conn:
        _add_column_if_missing(conn, "conversations", "name", "VARCHAR(256)")


def _add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        conn.commit()
        logger.info("Migration: added column %s.%s", table, column)
