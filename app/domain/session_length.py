"""Parse the learner's session length and decide when a session is winding down.

Session length is captured by the setup extractor under a `## Session length`
heading as "<number> <unit>" (e.g. "15 minutes", "1 hour") or "Not specified"
(see prompts/user-profile-extraction.md). This module turns that convention into
a number of minutes and a deterministic time-over flag.

Lesson timing is code-owned state — never inferred by the model (see
.notes/product-design.md "Lesson prompt architecture"). This module is pure
Layer A: no I/O, fully unit-testable.
"""

from __future__ import annotations

import re

DEFAULT_SESSION_MINUTES = 25  # design default when the learner didn't specify
WIND_DOWN_BUFFER_MINUTES = 3  # enter the closure/wind-down window this early

# Sane bounds for an in-chat session-length change. Anything outside is treated
# as nonsense ("11 years") and ignored — the stored length is left unchanged.
MIN_SESSION_MINUTES = 5
MAX_SESSION_MINUTES = 180

# Broad, inclusive pre-filter: does the learner's message even mention duration?
# It deliberately over-matches (units, bare numbers, adjustment words) so we
# never miss a real change request — the model does the precise intent check.
# A message with none of these cannot be a duration change, so we skip the call.
_DURATION_HINT_RE = re.compile(
    r"\b(\d{1,3}|min|mins|minute|minutes|hour|hours|hr|hrs|"
    r"longer|shorter|more|less|extend|shorten|quick|quickly|wrap|half)\b",
    re.IGNORECASE,
)

# Capture the body of the "## Session length" section up to the next H2 / EOF.
_SECTION_RE = re.compile(
    r"^##\s+Session length\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
# A number followed by a time unit; hours are normalised to minutes.
_VALUE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b",
    re.IGNORECASE,
)


def parse_session_length_minutes(
    profile_text: str | None, default: int = DEFAULT_SESSION_MINUTES
) -> int:
    """Return the learner's session length in minutes, or `default` if absent.

    Reads only the `## Session length` section to avoid matching stray numbers
    elsewhere in the profile. "Not specified" (or anything unparseable) → default.
    """
    if not profile_text:
        return default
    section = _SECTION_RE.search(profile_text)
    if not section:
        return default
    match = _VALUE_RE.search(section.group(1))
    if not match:
        return default
    value = float(match.group(1))
    minutes = value * 60 if match.group(2).lower().startswith("h") else value
    minutes = int(round(minutes))
    return minutes if minutes > 0 else default


def mentions_duration(text: str | None) -> bool:
    """Cheap pre-filter: True if the message could plausibly be about duration.

    Over-matches on purpose (see _DURATION_HINT_RE). A False here means the model
    extraction can be safely skipped — there is nothing duration-related to read.
    """
    if not text:
        return False
    return _DURATION_HINT_RE.search(text) is not None


def parse_extracted_minutes(
    raw: str | None,
    low: int = MIN_SESSION_MINUTES,
    high: int = MAX_SESSION_MINUTES,
) -> int | None:
    """Validate the extractor's output into a sane new length, or None for no change.

    The model returns a bare integer or "NONE". Anything that isn't an integer
    inside [low, high] — "NONE", prose, or a nonsensical value like 660 — yields
    None, meaning the stored session length is left unchanged.
    """
    if not raw:
        return None
    token = raw.strip().split()[0] if raw.strip() else ""
    try:
        minutes = int(token)
    except ValueError:
        return None
    return minutes if low <= minutes <= high else None


def is_time_over(
    elapsed_minutes: float,
    session_length_minutes: int,
    buffer_minutes: int = WIND_DOWN_BUFFER_MINUTES,
) -> bool:
    """True once the session has entered its wind-down window.

    The window opens `buffer_minutes` before the configured length so the tutor
    can wrap up gracefully rather than cut off at the hard limit.
    """
    return elapsed_minutes >= max(0, session_length_minutes - buffer_minutes)
