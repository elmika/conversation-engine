"""SQLAlchemy implementation of consent-record persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.infra.persistence.models import ConsentRecord


class SQLAlchemyConsentRepo:
    """Consent-record persistence using SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_consented_at(self, user_id: str) -> Optional[datetime]:
        record = self._session.get(ConsentRecord, user_id)
        return record.consented_at if record else None

    def has_consented(self, user_id: str) -> bool:
        return self._session.get(ConsentRecord, user_id) is not None

    def record(self, user_id: str) -> None:
        """Record consent for user_id. Idempotent — re-recording is a no-op,
        so a learner re-submitting (double-click, retry) doesn't overwrite the
        original timestamp."""
        if self._session.get(ConsentRecord, user_id) is not None:
            return
        self._session.add(ConsentRecord(user_id=user_id))
