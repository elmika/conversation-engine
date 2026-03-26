"""Unit tests for prompt_template module."""

import pytest

from app.domain.prompt_template import PromptTemplateError, render_prompt, validate_template

CONTEXT = {
    "time:current": "2026-03-26 21:42 UTC",
    "time:conversation-start": "2026-03-26 10:00 UTC",
    "time:lesson-time-spent": "5 minutes 30 seconds",
}


# --- validate_template ---

def test_validate_no_tags():
    validate_template("You are a helpful assistant.")


def test_validate_known_tags():
    validate_template("Now: {{time:current}}, start: {{time:conversation-start}}.")


def test_validate_malformed_no_colon():
    with pytest.raises(PromptTemplateError, match="Malformed tag"):
        validate_template("The time is {{current}}.")


def test_validate_unknown_namespace():
    with pytest.raises(PromptTemplateError, match="Unknown namespace 'foo'"):
        validate_template("{{foo:bar}}")


def test_validate_unknown_tag_in_known_namespace():
    with pytest.raises(PromptTemplateError, match="Unknown tag '{{time:whatever}}'"):
        validate_template("{{time:whatever}}")


def test_validate_multiple_valid_tags():
    validate_template("Start: {{time:conversation-start}}. Now: {{time:current}}.")


def test_validate_valid_and_invalid_raises():
    with pytest.raises(PromptTemplateError):
        validate_template("{{time:current}} and {{time:bad}}")


# --- render_prompt ---

def test_render_no_tags():
    result = render_prompt("Hello world.", CONTEXT)
    assert result == "Hello world."


def test_render_time_current():
    result = render_prompt("Current time: {{time:current}}.", CONTEXT)
    assert result == "Current time: 2026-03-26 21:42 UTC."


def test_render_conversation_start():
    result = render_prompt("Started: {{time:conversation-start}}.", CONTEXT)
    assert result == "Started: 2026-03-26 10:00 UTC."


def test_render_multiple_tags():
    result = render_prompt(
        "Now: {{time:current}}, start: {{time:conversation-start}}.", CONTEXT
    )
    assert result == "Now: 2026-03-26 21:42 UTC, start: 2026-03-26 10:00 UTC."


def test_render_repeated_tag():
    result = render_prompt("{{time:current}} and again {{time:current}}.", CONTEXT)
    assert result == "2026-03-26 21:42 UTC and again 2026-03-26 21:42 UTC."


def test_render_malformed_tag_raises():
    with pytest.raises(PromptTemplateError, match="Malformed tag"):
        render_prompt("{{current}}", CONTEXT)


def test_render_unknown_namespace_raises():
    with pytest.raises(PromptTemplateError, match="Unknown namespace"):
        render_prompt("{{foo:bar}}", CONTEXT)


def test_render_unknown_tag_raises():
    with pytest.raises(PromptTemplateError, match="Unknown tag"):
        render_prompt("{{time:whatever}}", CONTEXT)


def test_render_valid_and_invalid_raises():
    with pytest.raises(PromptTemplateError):
        render_prompt("{{time:current}} and {{current}}", CONTEXT)


def test_render_lesson_time_spent():
    result = render_prompt("Time spent: {{time:lesson-time-spent}}.", CONTEXT)
    assert result == "Time spent: 5 minutes 30 seconds."


def test_validate_lesson_time_spent():
    validate_template("Time so far: {{time:lesson-time-spent}}.")


def test_render_all_three_time_tags():
    result = render_prompt(
        "Start: {{time:conversation-start}}. Now: {{time:current}}. Spent: {{time:lesson-time-spent}}.",
        CONTEXT,
    )
    assert result == "Start: 2026-03-26 10:00 UTC. Now: 2026-03-26 21:42 UTC. Spent: 5 minutes 30 seconds."
