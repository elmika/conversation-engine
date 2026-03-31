"""Unit tests for prompt_template module."""

import pytest

from app.domain.prompt_template import PromptTemplateError, render_prompt, resolve_file_sections, validate_template

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


def test_validate_section_tags():
    validate_template("{{course}}\n\n{{user}}\n\n{{progress}}")


def test_validate_section_tag_course():
    validate_template("Context: {{course}}")


def test_validate_malformed_no_colon():
    with pytest.raises(PromptTemplateError, match="Malformed tag"):
        validate_template("The time is {{current}}.")


def test_validate_malformed_no_colon_lists_valid_section_tags():
    with pytest.raises(PromptTemplateError, match="{{course}}"):
        validate_template("{{unknown}}")


def test_validate_time_current_still_passes():
    validate_template("{{time:current}}")


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


# --- resolve_file_sections ---

def _make_loader(files: dict) -> object:
    def loader(tag: str):
        return files.get(tag)
    return loader


def test_resolve_no_section_tags():
    result = resolve_file_sections("No tags here.", _make_loader({}))
    assert result == "No tags here."


def test_resolve_course_tag():
    loader = _make_loader({"course": "# Course Content"})
    result = resolve_file_sections("Intro: {{course}}", loader)
    assert result == "Intro: # Course Content"


def test_resolve_user_tag():
    loader = _make_loader({"user": "Senior engineer"})
    result = resolve_file_sections("User: {{user}}", loader)
    assert result == "User: Senior engineer"


def test_resolve_progress_tag():
    loader = _make_loader({"progress": "Module 3"})
    result = resolve_file_sections("Progress: {{progress}}", loader)
    assert result == "Progress: Module 3"


def test_resolve_all_three_section_tags():
    loader = _make_loader({"course": "Course A", "user": "User B", "progress": "Prog C"})
    result = resolve_file_sections("{{course}} {{user}} {{progress}}", loader)
    assert result == "Course A User B Prog C"


def test_resolve_time_tag_passes_through():
    loader = _make_loader({})
    result = resolve_file_sections("Time: {{time:current}}", loader)
    assert result == "Time: {{time:current}}"


def test_resolve_missing_file_raises():
    loader = _make_loader({})
    with pytest.raises(PromptTemplateError, match="Section file not found"):
        resolve_file_sections("{{course}}", loader)


def test_resolve_section_containing_time_tag():
    loader = _make_loader({"course": "Now: {{time:current}}"})
    result = resolve_file_sections("{{course}}", loader)
    assert result == "Now: {{time:current}}"
