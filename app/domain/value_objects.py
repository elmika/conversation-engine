"""Domain value objects: immutable, validated business primitives."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MessageRole(str, Enum):
    """Valid message roles in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

    @classmethod
    def from_string(cls, role: str) -> MessageRole:
        """Parse a string into a MessageRole; raise ValueError if invalid."""
        try:
            return cls(role.lower())
        except ValueError:
            valid = ", ".join(r.value for r in cls)
            raise ValueError(f"Invalid role '{role}'. Must be one of: {valid}")


@dataclass(frozen=True)
class ConversationId:
    """
    Conversation identifier value object.
    
    Encapsulates generation and validation logic for conversation IDs.
    """

    value: str

    @classmethod
    def generate(cls) -> ConversationId:
        """Generate a new conversation ID."""
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> ConversationId:
        """
        Create ConversationId from a string.
        
        Validates that the string is a valid UUID format.
        Raises ValueError if invalid.
        """
        try:
            uuid.UUID(value)
        except ValueError as e:
            raise ValueError(f"Invalid conversation ID format: {value}") from e
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PromptSlug:
    """
    Prompt slug value object.
    
    Encapsulates validation logic for prompt slugs.
    """

    value: str

    @classmethod
    def from_string(cls, value: str, registry: dict[str, object]) -> PromptSlug:
        """
        Create PromptSlug from a string.
        
        Validates that the slug exists in the provided registry.
        Raises ValueError if the slug is not registered.
        """
        if value not in registry:
            valid = ", ".join(registry.keys())
            raise ValueError(f"Unknown prompt slug '{value}'. Valid slugs: {valid}")
        return cls(value=value)

    @classmethod
    def from_string_or_default(
        cls, value: Optional[str], default: str, registry: dict[str, object]
    ) -> PromptSlug:
        """
        Create PromptSlug from an optional string, falling back to default.
        
        If value is None, uses the default slug.
        Validates that the resulting slug exists in the registry.
        """
        slug = value or default
        return cls.from_string(slug, registry)

    def __str__(self) -> str:
        return self.value
