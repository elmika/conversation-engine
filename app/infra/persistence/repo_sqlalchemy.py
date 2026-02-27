"""SQLAlchemy implementation of the ConversationRepo port."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports import ConversationRepo
from app.infra.persistence.models import Conversation, Message, Run


class SQLAlchemyConversationRepo(ConversationRepo):
    """Conversation persistence using SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_conversation(self) -> str:
        """Create a new conversation with a generated ID; return its id."""
        conv_id = str(uuid.uuid4())
        self.create_conversation_with_id(conv_id)
        return conv_id

    def create_conversation_with_id(self, conversation_id: str) -> None:
        """Create a new conversation with a specific ID (domain-generated)."""
        conv = Conversation(id=conversation_id)
        self._session.add(conv)
        # No commit - UnitOfWork handles transaction boundaries

    def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [{"role": m.role, "content": m.content} for m in rows]

    def append_message(self, conversation_id: str, role: str, content: str) -> int:
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        self._session.add(msg)
        self._session.flush()  # Flush to get the auto-generated ID
        return msg.id

    def record_run(
        self,
        conversation_id: str,
        assistant_message_id: int,
        prompt_slug: str,
        model: str,
        ttfb_ms: int,
        total_ms: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        finish_reason: Optional[str] = None,
    ) -> None:
        run = Run(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            prompt_slug=prompt_slug,
            model=model,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
        )
        self._session.add(run)
        # No commit - UnitOfWork handles transaction boundaries

