"""Framing answer check: did the learner's reply actually answer the pending
setup question, or was it a clarifying question / off-topic aside?

`setup_flow.py::setup_phase_for_turn` counts raw learner turns and assumes
each one answers the fixed framing sequence (name, work, motivation, session
length) 1:1. A clarifying question back to the tutor breaks that assumption:
it consumes a turn slot without answering anything, so the *next* reply (the
real answer) lands on the wrong slot and the flow can advance to OUTLINE
having silently skipped a question — this is how session length went
unasked in a real session (2026-09-17).

Code still owns the phase-advance decision deterministically (turn count vs.
a required threshold); this module only judges whether to bump that
threshold, the same "model nudges code-owned state" shape as
objective_guard.py and closure_continuation.py. Pure Layer A — no I/O.
"""

from __future__ import annotations


def parse_framing_answer_result(raw: str | None) -> bool:
    """True (answered) unless the model clearly says NO.

    Defaults to "answered" on anything unparseable/unsure: a false negative
    here just re-asks a question the learner already answered (mildly
    redundant); a false positive reproduces the original bug (a real
    non-answer silently consumes a framing slot). Bias accordingly.
    """
    if not raw:
        return True
    return not raw.strip().upper().startswith("NO")
