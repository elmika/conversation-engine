"""Objective guard: has the current module's objective been met this session?

A single-purpose model guard (see .notes/product-design.md "Lesson prompt
architecture"). Code owns *when* it runs (only after the lesson has developed for
a few turns) and *how its verdict is parsed*; the model owns only the yes/no
judgment over the transcript. Pure Layer A — no I/O.
"""

from __future__ import annotations

# Don't judge completion before the lesson has had room to develop. Bounds cost
# (no guard call on the first turns) and prevents premature closure.
OBJECTIVE_GUARD_MIN_TURNS = 4


def parse_objective_result(raw: str | None) -> bool:
    """True only if the guard clearly says YES; anything else (incl. unsure) is False."""
    return bool(raw) and raw.strip().upper().startswith("YES")
