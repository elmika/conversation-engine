"""SQLAlchemy Unit of Work implementation."""

from __future__ import annotations

from types import TracebackType
from typing import Optional

from sqlalchemy.orm import Session

from app.application.ports import ConversationRepo, UnitOfWork
from app.infra.persistence.repo_sqlalchemy import SQLAlchemyConversationRepo


class SQLAlchemyUnitOfWork(UnitOfWork):
    """
    SQLAlchemy implementation of Unit of Work pattern.
    
    Manages the session lifecycle and transaction boundaries.
    The repository does NOT commit; only the UoW commits or rolls back.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self.repo: ConversationRepo = SQLAlchemyConversationRepo(session)

    def commit(self) -> None:
        """Commit the current transaction."""
        self._session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._session.rollback()

    def __enter__(self) -> SQLAlchemyUnitOfWork:
        """Enter context manager; return self for access to repo."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Exit context manager.
        
        Automatically rollback on exception, otherwise do nothing.
        The caller must explicitly call commit() if they want to persist changes.
        """
        if exc_type is not None:
            self.rollback()
