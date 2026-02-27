"""Domain logic for conversation history management."""

import logging
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class HistoryTrimResult(TypedDict):
    """Result of trimming history with statistics."""

    messages: list[dict[str, str]]
    was_trimmed: bool
    original_count: int
    trimmed_count: int
    original_turns: int
    trimmed_turns: int
    original_tokens: int
    trimmed_tokens: int


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text using a simple heuristic.
    
    OpenAI's rule of thumb: 1 token ≈ 4 characters for English text.
    This is conservative (overestimates slightly) which is safer for limits.
    
    For production, consider using tiktoken library for accurate counts.
    """
    return len(text) // 4 + 1


def trim_history(
    messages: list[dict[str, str]],
    max_turns: Optional[int] = None,
    max_tokens: Optional[int] = None,
    conversation_id: Optional[str] = None,
) -> HistoryTrimResult:
    """
    Trim conversation history to stay within turn and token limits.
    
    Strategy:
    1. Keep the most recent messages (LIFO)
    2. Count in pairs (user + assistant = 1 turn)
    3. Stop when either limit is exceeded
    
    Logs when trimming occurs for monitoring and alerting.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        max_turns: Maximum number of turns (user+assistant pairs) to keep
        max_tokens: Maximum total tokens to keep
        conversation_id: Optional conversation ID for logging context
        
    Returns:
        HistoryTrimResult with trimmed messages and statistics
        
    Examples:
        >>> msgs = [
        ...     {"role": "user", "content": "Hi"},
        ...     {"role": "assistant", "content": "Hello"},
        ...     {"role": "user", "content": "How are you?"},
        ...     {"role": "assistant", "content": "I'm good"},
        ... ]
        >>> result = trim_history(msgs, max_turns=1)
        >>> result["messages"]  # Keep only last turn
        [{"role": "user", "content": "How are you?"}, {"role": "assistant", "content": "I'm good"}]
        >>> result["was_trimmed"]
        True
    """
    # Calculate original stats
    original_stats = get_history_stats(messages)
    if not messages:
        return HistoryTrimResult(
            messages=[],
            was_trimmed=False,
            original_count=0,
            trimmed_count=0,
            original_turns=0,
            trimmed_turns=0,
            original_tokens=0,
            trimmed_tokens=0,
        )
    
    # If no limits, return all messages
    if max_turns is None and max_tokens is None:
        return HistoryTrimResult(
            messages=messages,
            was_trimmed=False,
            original_count=original_stats["message_count"],
            trimmed_count=original_stats["message_count"],
            original_turns=original_stats["turn_count"],
            trimmed_turns=original_stats["turn_count"],
            original_tokens=original_stats["estimated_tokens"],
            trimmed_tokens=original_stats["estimated_tokens"],
        )
    
    # Work backwards from most recent message
    kept_messages: list[dict[str, str]] = []
    turn_count = 0
    token_count = 0
    
    # Track if we're in the middle of a turn (saw assistant but not user yet)
    pending_assistant: Optional[dict[str, str]] = None
    
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.get("content", ""))
        role = msg.get("role")
        
        if role == "assistant":
            # Save assistant message, wait for its user message
            pending_assistant = msg
            continue
        elif role == "user":
            # Found user message - this completes a turn
            turn_count += 1
            
            # Check turn limit
            if max_turns is not None and turn_count > max_turns:
                break
            
            # Calculate tokens for this complete turn
            user_tokens = msg_tokens
            assistant_tokens = estimate_tokens(pending_assistant.get("content", "")) if pending_assistant else 0
            turn_tokens = user_tokens + assistant_tokens
            
            # Check token limit
            if max_tokens is not None and token_count + turn_tokens > max_tokens:
                break
            
            # Add both messages in reverse order (assistant first since we're going backwards)
            if pending_assistant:
                kept_messages.append(pending_assistant)
                token_count += assistant_tokens
                pending_assistant = None
            
            kept_messages.append(msg)
            token_count += user_tokens
    
    # Reverse back to chronological order
    trimmed_messages = list(reversed(kept_messages))
    
    # Calculate trimmed stats
    trimmed_stats = get_history_stats(trimmed_messages)
    was_trimmed = len(trimmed_messages) < len(messages)
    
    # Log if trimming occurred
    if was_trimmed:
        log_extra = {
            "conversation_id": conversation_id,
            "original_messages": original_stats["message_count"],
            "trimmed_messages": trimmed_stats["message_count"],
            "original_turns": original_stats["turn_count"],
            "trimmed_turns": trimmed_stats["turn_count"],
            "original_tokens": original_stats["estimated_tokens"],
            "trimmed_tokens": trimmed_stats["estimated_tokens"],
            "max_turns": max_turns,
            "max_tokens": max_tokens,
        }
        logger.warning(
            f"History trimmed: {original_stats['message_count']} → {trimmed_stats['message_count']} messages, "
            f"{original_stats['turn_count']} → {trimmed_stats['turn_count']} turns, "
            f"{original_stats['estimated_tokens']} → {trimmed_stats['estimated_tokens']} tokens",
            extra=log_extra,
        )
    
    return HistoryTrimResult(
        messages=trimmed_messages,
        was_trimmed=was_trimmed,
        original_count=original_stats["message_count"],
        trimmed_count=trimmed_stats["message_count"],
        original_turns=original_stats["turn_count"],
        trimmed_turns=trimmed_stats["turn_count"],
        original_tokens=original_stats["estimated_tokens"],
        trimmed_tokens=trimmed_stats["estimated_tokens"],
    )


def get_history_stats(messages: list[dict[str, str]]) -> dict[str, int]:
    """
    Get statistics about conversation history.
    
    Returns dict with:
        - message_count: Total number of messages
        - turn_count: Number of turns (user+assistant pairs)
        - estimated_tokens: Estimated total token count
    """
    if not messages:
        return {"message_count": 0, "turn_count": 0, "estimated_tokens": 0}
    
    message_count = len(messages)
    estimated_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
    
    # Count turns (user messages)
    turn_count = sum(1 for m in messages if m.get("role") == "user")
    
    return {
        "message_count": message_count,
        "turn_count": turn_count,
        "estimated_tokens": estimated_tokens,
    }
