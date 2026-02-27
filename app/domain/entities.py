"""Domain entities: business objects with identity and behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.domain.value_objects import ConversationId, MessageRole


@dataclass(frozen=True)
class Message:
    """
    Domain message entity.
    
    Represents a single message in a conversation with validated role and content.
    """

    role: MessageRole
    content: str
    id: Optional[int] = None

    @classmethod
    def create(cls, role: str, content: str, id: Optional[int] = None) -> Message:
        """
        Create a Message with validated role.
        
        Raises ValueError if role is invalid.
        """
        validated_role = MessageRole.from_string(role)
        if not content or not content.strip():
            raise ValueError("Message content cannot be empty")
        return cls(role=validated_role, content=content, id=id)

    def to_dict(self) -> dict[str, str]:
        """Convert to dict format for LLM API calls."""
        return {"role": self.role.value, "content": self.content}


@dataclass
class ConversationTurn:
    """
    Domain representation of a conversation turn.
    
    A turn consists of one or more user messages followed by an assistant response.
    This is a value object that represents the business concept of a "turn" in a conversation.
    """

    user_messages: list[Message]
    assistant_message: Optional[Message] = None

    def __post_init__(self) -> None:
        """Validate turn invariants."""
        if not self.user_messages:
            raise ValueError("A turn must have at least one user message")
        for msg in self.user_messages:
            if msg.role != MessageRole.USER:
                raise ValueError(f"Turn user_messages must have role 'user', got '{msg.role.value}'")
        if self.assistant_message and self.assistant_message.role != MessageRole.ASSISTANT:
            raise ValueError(
                f"Turn assistant_message must have role 'assistant', got '{self.assistant_message.role.value}'"
            )

    def all_messages(self) -> list[Message]:
        """Return all messages in this turn (user messages + optional assistant message)."""
        if self.assistant_message:
            return self.user_messages + [self.assistant_message]
        return list(self.user_messages)


@dataclass
class Conversation:
    """
    Domain aggregate root for a conversation.
    
    Encapsulates conversation identity and the history of turns.
    Enforces business rules about conversation structure.
    """

    id: ConversationId
    turns: list[ConversationTurn] = field(default_factory=list)

    @classmethod
    def create_new(cls) -> Conversation:
        """Create a new conversation with a generated ID."""
        return cls(id=ConversationId.generate())

    @classmethod
    def from_existing(cls, conversation_id: str, messages: list[Message]) -> Conversation:
        """
        Reconstruct a conversation from persistence.
        
        Groups messages into turns (user messages followed by assistant response).
        """
        conv_id = ConversationId.from_string(conversation_id)
        turns = cls._group_messages_into_turns(messages)
        return cls(id=conv_id, turns=turns)

    @staticmethod
    def _group_messages_into_turns(messages: list[Message]) -> list[ConversationTurn]:
        """
        Group messages into turns.
        
        A turn is one or more user messages followed by an optional assistant message.
        This is a simplified grouping; in practice, conversations may have complex patterns.
        """
        turns: list[ConversationTurn] = []
        current_user_messages: list[Message] = []

        for msg in messages:
            if msg.role == MessageRole.USER:
                current_user_messages.append(msg)
            elif msg.role == MessageRole.ASSISTANT:
                if current_user_messages:
                    turns.append(ConversationTurn(
                        user_messages=current_user_messages,
                        assistant_message=msg,
                    ))
                    current_user_messages = []

        if current_user_messages:
            turns.append(ConversationTurn(user_messages=current_user_messages))

        return turns

    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a new turn to the conversation."""
        self.turns.append(turn)

    def get_all_messages(self) -> list[Message]:
        """Return all messages across all turns in chronological order."""
        result: list[Message] = []
        for turn in self.turns:
            result.extend(turn.all_messages())
        return result

    def get_message_count(self) -> int:
        """Return total number of messages in the conversation."""
        return sum(len(turn.all_messages()) for turn in self.turns)
