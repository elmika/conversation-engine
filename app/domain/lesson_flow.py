"""Lesson flow: maps a lesson phase to the prompt slug that drives it.

A lesson has three moments — introduction, core, closure — each its own
single-purpose prompt (see .notes/product-design.md "Lesson prompt architecture").

Which phase a turn belongs to is decided in CODE from deterministic state
(turn position now; time-over / objective guard later) — never inferred by the
model. This module owns only the pure mappings:

  - phase  → prompt slug   (resolve_phase_prompt)
  - turn   → phase         (phase_for_turn)

Phase *selection* that needs runtime state (history, time, guard result) lives in
the service; this module stays a pure, fully unit-testable Layer A unit.
"""

from __future__ import annotations

from enum import Enum


class LessonPhase(str, Enum):
    INTRO = "intro"
    CORE = "core"
    CLOSURE = "closure"


# Flows that have distinct per-phase prompts, keyed by the flow id stored on the
# conversation (`conversations.prompt_slug`). The flow id IS the intro prompt
# slug — "course-session-init" both names the flow and drives its opening turn.
#
# CORE is the required baseline of every flow: any phase without a dedicated
# prompt falls back to it. Any slug NOT listed here is a "flat" prompt (setup,
# default, ad-hoc admin prompts) where every phase resolves to that one slug.
_LESSON_FLOWS: dict[str, dict[LessonPhase, str]] = {
    "course-session-init": {
        LessonPhase.INTRO: "course-session-init",
        LessonPhase.CORE: "course-session-core",
        LessonPhase.CLOSURE: "course-session-closure",
    },
}


def is_lesson_flow(flow_slug: str) -> bool:
    """True if the slug names a multi-phase lesson flow (vs. a flat prompt)."""
    return flow_slug in _LESSON_FLOWS


def resolve_phase_prompt(flow_slug: str, phase: LessonPhase) -> str:
    """Return the prompt slug driving `phase` of `flow_slug`.

    Flat (non-lesson) prompts resolve every phase to the slug itself, so the
    caller can treat all conversations uniformly. Lesson phases without a
    dedicated prompt fall back to the flow's CORE prompt.
    """
    flow = _LESSON_FLOWS.get(flow_slug)
    if flow is None:
        return flow_slug
    return flow.get(phase) or flow[LessonPhase.CORE]


def phase_for_turn(is_opening_turn: bool) -> LessonPhase:
    """Map deterministic turn position to a lesson phase.

    The opening turn (AI-initiated, no prior history) is the INTRO; every
    subsequent turn is CORE. CLOSURE is selected separately once the time-over
    flag and objective guard exist — deferred, so not produced here yet.
    """
    return LessonPhase.INTRO if is_opening_turn else LessonPhase.CORE
