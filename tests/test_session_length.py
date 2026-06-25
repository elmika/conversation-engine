"""Layer A tests: pure session-length parsing and time-over decision.

No LLM, no DB — fully deterministic, runs in CI on every commit.
"""

import pytest

from app.domain.session_length import (
    DEFAULT_SESSION_MINUTES,
    is_time_over,
    parse_session_length_minutes,
)

_PROFILE = """## Name
Mika

## Session length
{value}

## Other context
Not yet provided.
"""


class TestParseSessionLength:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("15 minutes", 15),
            ("45 minutes", 45),
            ("30 min", 30),
            ("20m", 20),
            ("1 hour", 60),
            ("2 hours", 120),
            ("1.5 hours", 90),
            ("1 hr", 60),
        ],
    )
    def test_parses_number_and_unit(self, value, expected):
        assert parse_session_length_minutes(_PROFILE.format(value=value)) == expected

    @pytest.mark.parametrize("value", ["Not specified", "Not yet provided.", "whenever"])
    def test_unparseable_value_falls_back_to_default(self, value):
        assert parse_session_length_minutes(_PROFILE.format(value=value)) == DEFAULT_SESSION_MINUTES

    def test_missing_section_falls_back_to_default(self):
        assert parse_session_length_minutes("## Name\nMika\n") == DEFAULT_SESSION_MINUTES

    def test_none_or_empty_falls_back_to_default(self):
        assert parse_session_length_minutes(None) == DEFAULT_SESSION_MINUTES
        assert parse_session_length_minutes("") == DEFAULT_SESSION_MINUTES

    def test_does_not_match_numbers_outside_the_section(self):
        # "20 years" in Work must not be read as the session length.
        profile = "## Work\n20 years as an engineer\n\n## Session length\n15 minutes\n"
        assert parse_session_length_minutes(profile) == 15

    def test_custom_default(self):
        assert parse_session_length_minutes(None, default=10) == 10


class TestIsTimeOver:
    def test_false_well_within_session(self):
        # 5 min into a 25-min session (window opens at 22) → not over.
        assert is_time_over(elapsed_minutes=5, session_length_minutes=25) is False

    def test_true_inside_wind_down_window(self):
        # 23 min into a 25-min session (window opens at 22) → winding down.
        assert is_time_over(elapsed_minutes=23, session_length_minutes=25) is True

    def test_true_past_the_limit(self):
        assert is_time_over(elapsed_minutes=40, session_length_minutes=25) is True

    def test_buffer_is_configurable(self):
        assert is_time_over(elapsed_minutes=18, session_length_minutes=25, buffer_minutes=10) is True
        assert is_time_over(elapsed_minutes=14, session_length_minutes=25, buffer_minutes=10) is False

    def test_never_negative_window(self):
        # Tiny session shorter than the buffer → over from the start.
        assert is_time_over(elapsed_minutes=0, session_length_minutes=2) is True
