"""Closure continuation: did the learner ask to keep going past a closure invite?

Closure is a suggestion, not a cutoff — see prompts/course-session-closure.md.
Ending the session is still a deliberate action (the "End Session" button /
endpoint); this module only decides whether to route the *next chat turn*
back to CORE instead of staying latched in CLOSURE. Pure Layer A — no I/O.
"""

from __future__ import annotations

import re

# How much extra runway a confirmed "let's keep going" buys, in minutes added
# to session_length_minutes. Reuses the existing in-chat session-length
# mechanism (app.learning.session_length) so the effect is the same one
# learners already see when they ask for more time.
CONTINUE_EXTENSION_MINUTES = 10

# Broad, inclusive pre-filter: could this reply plausibly be asking to keep
# learning? Over-matches on purpose — the model call does the precise intent
# check, this just avoids spending it on replies that obviously aren't this
# ("thanks!", "sounds good", "bye").
_CONTINUE_HINT_RE = re.compile(
    r"\b(keep going|keep learning|continue|one more|not (done|ready|finished)|"
    r"don'?t stop|before (we|I) stop|actually|can we|let'?s keep|"
    r"want to (keep|continue)|not yet|hold on)\b",
    re.IGNORECASE,
)


def mentions_continue_intent(text: str | None) -> bool:
    """Cheap pre-filter: True if the reply could plausibly ask to continue."""
    if not text:
        return False
    return _CONTINUE_HINT_RE.search(text) is not None


def parse_continue_result(raw: str | None) -> bool:
    """True only if the model clearly says YES; anything else is False."""
    return bool(raw) and raw.strip().upper().startswith("YES")
