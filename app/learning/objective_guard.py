"""Objective guard: has the current module's objective been met this session?

A single-purpose model guard (see .notes/product-design.md "Lesson prompt
architecture"). Code owns *when* it runs (only after the lesson has developed for
a few turns) and *how its verdict is parsed*; the model owns only the yes/no
judgment over the transcript. Pure Layer A — no I/O.
"""

from __future__ import annotations

# Don't judge completion before the lesson has had room to develop. Bounds cost
# (no guard call on the first turns) and prevents premature closure. This is
# also the floor for objective_guard_min_turns below.
OBJECTIVE_GUARD_MIN_TURNS = 4

# Assumed wall-clock cost of one question-answer exchange (read the tutor's
# turn, think, answer) with the short, question-led course-session-core
# turns — see docs/socratic-tutor-plan.md. Used only to scale the guard's
# min-turns floor to the session's planned length, not for real timing.
MINUTES_PER_EXCHANGE = 2


def objective_guard_min_turns(session_length_minutes: int | None) -> int:
    """Minimum learner turns before the objective guard may fire.

    A fixed floor (OBJECTIVE_GUARD_MIN_TURNS) under-serves long sessions: a
    30-minute session and a 10-minute one shouldn't be eligible for closure
    at the same turn count. Scale the floor by the session's planned length
    instead, assuming MINUTES_PER_EXCHANGE per exchange. No upper cap — a
    longer session earns more room before the guard can even consider firing.
    """
    if not session_length_minutes:
        return OBJECTIVE_GUARD_MIN_TURNS
    return max(OBJECTIVE_GUARD_MIN_TURNS, session_length_minutes // MINUTES_PER_EXCHANGE)


def parse_objective_result(raw: str | None) -> bool:
    """True only if the guard clearly says YES; anything else (incl. unsure) is False."""
    return bool(raw) and raw.strip().upper().startswith("YES")
