"""Setup flow: maps a setup phase to the prompt slug that drives it.

The setup conversation has two moments — framing Q&A, then the course-outline
proposal — each its own single-purpose prompt, mirroring the lesson flow
pattern (see lesson_flow.py). Framing is a plain conversational Q&A and does
not need frontier-tier reasoning; the outline proposal is the one generation
in the whole flow worth paying for, since a learner spends their whole course
on it (see docs/roadmap.md item 1).

Which phase a turn belongs to is decided in CODE from deterministic state (a
fixed count of framing questions) — never inferred by the model, matching the
lesson flow's "code owns deterministic state" principle. This module owns only
the pure mapping:

  - phase              → prompt slug   (resolve_setup_phase_prompt)
  - total user turns   → phase         (setup_phase_for_turn)

Phase *selection* that needs runtime state (message history) lives in the
service; this module stays a pure, fully unit-testable Layer A unit.
"""

from __future__ import annotations

from enum import Enum

# The framing prompt (prompts/user-profile-collection.md) asks exactly this
# many questions, one per turn, in a fixed order: name, industry, motivation,
# session length. The 4th answer is the one that triggers the outline phase.
FRAMING_TURNS = 4


class SetupPhase(str, Enum):
    FRAMING = "framing"
    OUTLINE = "outline"


# Flows that have distinct per-phase prompts, keyed by the flow id stored on
# the conversation (`conversations.prompt_slug`). The flow id IS the framing
# prompt slug — "user-profile-collection" both names the flow and drives its
# opening turns.
_SETUP_FLOWS: dict[str, dict[SetupPhase, str]] = {
    "user-profile-collection": {
        SetupPhase.FRAMING: "user-profile-collection",
        SetupPhase.OUTLINE: "course-outline-proposal",
    },
}


def is_setup_flow(flow_slug: str) -> bool:
    """True if the slug names a multi-phase setup flow (vs. a flat prompt)."""
    return flow_slug in _SETUP_FLOWS


def resolve_setup_phase_prompt(flow_slug: str, phase: SetupPhase) -> str:
    """Return the prompt slug driving `phase` of `flow_slug`.

    Flows not registered here resolve to the slug itself, so the caller can
    treat all conversations uniformly.
    """
    flow = _SETUP_FLOWS.get(flow_slug)
    if flow is None:
        return flow_slug
    return flow[phase]


def setup_phase_for_turn(total_user_turns: int) -> SetupPhase:
    """Map a deterministic user-turn count to a setup phase.

    `total_user_turns` counts every user reply so far INCLUDING the one being
    answered right now (i.e. history + the incoming turn). Once the learner
    has answered all framing questions, this turn and every one after it
    resolves to OUTLINE — including follow-up refinement turns ("make module
    3 more advanced"), which should stay on the outline-quality model too.
    """
    return SetupPhase.OUTLINE if total_user_turns >= FRAMING_TURNS else SetupPhase.FRAMING
