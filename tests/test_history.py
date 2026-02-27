"""Tests for conversation history trimming."""

from app.domain.history import estimate_tokens, get_history_stats, trim_history


def test_estimate_tokens():
    """Token estimation uses 4 chars per token heuristic."""
    assert estimate_tokens("") == 1  # Minimum 1 token
    assert estimate_tokens("Hello") == 2  # 5 chars / 4 + 1 = 2
    assert estimate_tokens("Hello world") == 3  # 11 chars / 4 + 1 = 3
    assert estimate_tokens("a" * 100) == 26  # 100 / 4 + 1 = 26


def test_trim_history_no_limits():
    """When no limits are set, all messages are kept."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm good"},
    ]
    result = trim_history(messages, max_turns=None, max_tokens=None)
    assert result == messages


def test_trim_history_by_turns():
    """Trimming by turn count keeps most recent N turns."""
    messages = [
        {"role": "user", "content": "Turn 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Turn 2"},
        {"role": "assistant", "content": "Response 2"},
        {"role": "user", "content": "Turn 3"},
        {"role": "assistant", "content": "Response 3"},
    ]
    
    # Keep only last turn
    result = trim_history(messages, max_turns=1)
    assert len(result) == 2
    assert result[0]["content"] == "Turn 3"
    assert result[1]["content"] == "Response 3"
    
    # Keep last 2 turns
    result = trim_history(messages, max_turns=2)
    assert len(result) == 4
    assert result[0]["content"] == "Turn 2"
    assert result[3]["content"] == "Response 3"


def test_trim_history_by_tokens():
    """Trimming by token count keeps messages within budget."""
    messages = [
        {"role": "user", "content": "a" * 100},  # ~26 tokens
        {"role": "assistant", "content": "b" * 100},  # ~26 tokens
        {"role": "user", "content": "c" * 100},  # ~26 tokens
        {"role": "assistant", "content": "d" * 100},  # ~26 tokens
    ]
    
    # Keep only messages that fit in ~60 tokens (should keep last turn = 2 messages)
    result = trim_history(messages, max_tokens=60)
    assert len(result) == 2
    assert result[0]["content"] == "c" * 100
    assert result[1]["content"] == "d" * 100


def test_trim_history_preserves_turn_pairs():
    """Trimming preserves user+assistant pairs (doesn't break mid-turn)."""
    messages = [
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 100},
        {"role": "user", "content": "c" * 100},
        {"role": "assistant", "content": "d" * 100},
    ]
    
    # With reasonable token limit, should keep complete turn
    result = trim_history(messages, max_tokens=60)
    # Should keep the last turn (user + assistant)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"
    assert result[0]["content"] == "c" * 100
    assert result[1]["content"] == "d" * 100


def test_trim_history_empty_messages():
    """Trimming empty message list returns empty list."""
    result = trim_history([], max_turns=10, max_tokens=1000)
    assert result == []


def test_trim_history_both_limits():
    """When both limits are set, more restrictive one applies."""
    messages = [
        {"role": "user", "content": "a" * 100},  # ~26 tokens
        {"role": "assistant", "content": "b" * 100},  # ~26 tokens
        {"role": "user", "content": "c" * 100},  # ~26 tokens
        {"role": "assistant", "content": "d" * 100},  # ~26 tokens
        {"role": "user", "content": "e" * 100},  # ~26 tokens
        {"role": "assistant", "content": "f" * 100},  # ~26 tokens
    ]
    
    # Turn limit would allow 2 turns (4 messages), but token limit only allows ~2 messages
    result = trim_history(messages, max_turns=2, max_tokens=50)
    assert len(result) <= 4  # Turn limit
    # Token limit should be more restrictive here


def test_get_history_stats():
    """History stats returns accurate counts."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm good"},
    ]
    
    stats = get_history_stats(messages)
    assert stats["message_count"] == 4
    assert stats["turn_count"] == 2  # 2 user messages = 2 turns
    assert stats["estimated_tokens"] > 0


def test_get_history_stats_empty():
    """History stats for empty list returns zeros."""
    stats = get_history_stats([])
    assert stats["message_count"] == 0
    assert stats["turn_count"] == 0
    assert stats["estimated_tokens"] == 0


def test_trim_history_realistic_conversation():
    """Test with realistic conversation that exceeds limits."""
    # Simulate 15 turns (30 messages)
    messages = []
    for i in range(15):
        messages.append({"role": "user", "content": f"User message {i+1}" * 10})
        messages.append({"role": "assistant", "content": f"Assistant response {i+1}" * 10})
    
    # Trim to last 5 turns
    result = trim_history(messages, max_turns=5)
    assert len(result) == 10  # 5 turns = 10 messages
    # Should keep turns 11-15
    assert "User message 11" in result[0]["content"]
    assert "Assistant response 15" in result[-1]["content"]
