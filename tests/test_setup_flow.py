"""Layer A tests: pure phase→slug and turn-count→phase mappings for the setup flow.

No LLM, no DB — fully deterministic, runs in CI on every commit.
"""

import pytest

from app.learning.setup_flow import (
    FRAMING_TURNS,
    SetupPhase,
    is_setup_flow,
    resolve_setup_phase_prompt,
    setup_phase_for_turn,
)


class TestResolveSetupPhasePrompt:
    def test_framing_resolves_to_profile_collection_prompt(self):
        assert (
            resolve_setup_phase_prompt("user-profile-collection", SetupPhase.FRAMING)
            == "user-profile-collection"
        )

    def test_outline_resolves_to_outline_proposal_prompt(self):
        assert (
            resolve_setup_phase_prompt("user-profile-collection", SetupPhase.OUTLINE)
            == "course-outline-proposal"
        )

    @pytest.mark.parametrize("phase", list(SetupPhase))
    def test_flat_prompt_resolves_every_phase_to_itself(self, phase):
        # Lesson / default / ad-hoc prompts are not setup flows: identity mapping.
        assert resolve_setup_phase_prompt("course-session-init", phase) == "course-session-init"
        assert resolve_setup_phase_prompt("default", phase) == "default"


class TestFlowClassification:
    def test_profile_collection_is_a_setup_flow(self):
        assert is_setup_flow("user-profile-collection") is True

    def test_non_setup_prompts_are_not_setup_flows(self):
        assert is_setup_flow("course-session-init") is False
        assert is_setup_flow("default") is False
        # The outline-proposal prompt is a resolution target, not a flow id.
        assert is_setup_flow("course-outline-proposal") is False


class TestSetupPhaseForTurn:
    @pytest.mark.parametrize("turns", range(FRAMING_TURNS))
    def test_below_framing_turns_is_framing(self, turns):
        assert setup_phase_for_turn(turns) is SetupPhase.FRAMING

    def test_exactly_framing_turns_is_outline(self):
        assert setup_phase_for_turn(FRAMING_TURNS) is SetupPhase.OUTLINE

    def test_beyond_framing_turns_stays_outline(self):
        # Follow-up refinement turns ("make it shorter") stay on the outline prompt.
        assert setup_phase_for_turn(FRAMING_TURNS + 5) is SetupPhase.OUTLINE
