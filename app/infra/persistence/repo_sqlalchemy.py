"""SQLAlchemy implementation of the ConversationRepo port."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, func, select
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

    def list_conversations(self, page: int, page_size: int) -> tuple[list[dict], int]:
        """Return (rows, total) ordered by created_at DESC with pagination."""
        total = self._session.execute(select(func.count()).select_from(Conversation)).scalar_one()

        first_msg_sq = (
            select(Message.content)
            .where(Message.conversation_id == Conversation.id)
            .where(Message.role == "user")
            .order_by(Message.id.asc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        last_activity_sq = (
            select(func.max(Message.created_at))
            .where(Message.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
        )

        stmt = (
            select(
                Conversation,
                first_msg_sq.label("first_message"),
                last_activity_sq.label("last_activity"),
            )
            .order_by(Conversation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = self._session.execute(stmt).all()
        return [
            {
                "id": r.Conversation.id,
                "name": r.Conversation.name,
                "created_at": r.Conversation.created_at.isoformat(),
                "last_activity": (r.last_activity or r.Conversation.created_at).isoformat(),
                "first_message": (r.first_message or "")[:120],
            }
            for r in rows
        ], total

    def rename_conversation(self, conversation_id: str, name: str) -> None:
        conv = self._session.get(Conversation, conversation_id)
        if conv:
            conv.name = name

    def delete_conversation(self, conversation_id: str) -> None:
        conv = self._session.get(Conversation, conversation_id)
        if conv:
            self._session.delete(conv)

    def truncate_from(self, conversation_id: str, message_id: int) -> None:
        """Delete messages with id >= message_id and their associated runs."""
        # Delete runs referencing messages that will be deleted
        msg_ids_sq = (
            select(Message.id)
            .where(Message.conversation_id == conversation_id)
            .where(Message.id >= message_id)
        )
        self._session.execute(delete(Run).where(Run.assistant_message_id.in_(msg_ids_sq)))
        self._session.execute(
            delete(Message).where(
                Message.conversation_id == conversation_id,
                Message.id >= message_id,
            )
        )

    def get_messages_with_metadata(self, conversation_id: str) -> list[dict]:
        """Return [{id, role, content, created_at}] ordered by id ASC."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]

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

