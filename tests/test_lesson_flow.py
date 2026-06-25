"""Layer A tests: pure phase→slug and turn→phase mappings for lesson flows.

No LLM, no DB — fully deterministic, runs in CI on every commit.
"""

import pytest

from app.domain.lesson_flow import (
    LessonPhase,
    is_lesson_flow,
    phase_for_turn,
    resolve_phase_prompt,
)


class TestResolvePhasePrompt:
    def test_intro_resolves_to_init_prompt(self):
        # The flow id is also the intro prompt slug.
        assert resolve_phase_prompt("course-session-init", LessonPhase.INTRO) == "course-session-init"

    def test_core_resolves_to_core_prompt(self):
        assert resolve_phase_prompt("course-session-init", LessonPhase.CORE) == "course-session-core"

    def test_closure_resolves_to_closure_prompt(self):
        assert resolve_phase_prompt("course-session-init", LessonPhase.CLOSURE) == "course-session-closure"

    @pytest.mark.parametrize("phase", list(LessonPhase))
    def test_flat_prompt_resolves_every_phase_to_itself(self, phase):
        # Setup / default / ad-hoc prompts are not lesson flows: identity mapping.
        assert resolve_phase_prompt("user-profile-collection", phase) == "user-profile-collection"
        assert resolve_phase_prompt("default", phase) == "default"


class TestFlowClassification:
    def test_course_session_is_a_lesson_flow(self):
        assert is_lesson_flow("course-session-init") is True

    def test_flat_prompts_are_not_lesson_flows(self):
        assert is_lesson_flow("user-profile-collection") is False
        assert is_lesson_flow("default") is False
        # The core prompt is a resolution target, not a flow id.
        assert is_lesson_flow("course-session-core") is False


class TestPhaseForTurn:
    def test_opening_turn_is_intro(self):
        assert phase_for_turn(is_opening_turn=True) is LessonPhase.INTRO

    def test_subsequent_turn_is_core(self):
        assert phase_for_turn(is_opening_turn=False) is LessonPhase.CORE
