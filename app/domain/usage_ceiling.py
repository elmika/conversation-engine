"""Usage-cap enforcement decision: pure numbers in, decision out — no DB/HTTP knowledge."""

from __future__ import annotations

from typing import Literal

CapScope = Literal["session", "user_daily", "platform_daily"]


class CapExceeded(Exception):
    """Raised when a $ spend ceiling has been crossed."""

    def __init__(self, scope: CapScope) -> None:
        self.scope = scope
        super().__init__(f"usage cap exceeded: {scope}")


CAP_MESSAGES: dict[CapScope, str] = {
    "session": (
        "This session has reached its usage limit — please start a new session to continue."
    ),
    "user_daily": "You've reached today's usage limit — please try again tomorrow.",
    "platform_daily": (
        "SkillForge has hit today's usage limit platform-wide — please try again tomorrow."
    ),
}


def cap_message(scope: CapScope) -> str:
    """Friendly, product-owned message shown to the learner when a cap is hit."""
    return CAP_MESSAGES[scope]


def check_caps(
    *,
    session_spend_usd: float,
    user_daily_spend_usd: float,
    platform_daily_spend_usd: float,
    session_cap_usd: float,
    user_daily_cap_usd: float,
    platform_daily_cap_usd: float,
) -> None:
    """Raise CapExceeded(scope) for the first cap crossed, checked platform -> user -> session.

    Platform is checked first since it's the "pause everything" condition and should
    produce the platform-scoped message regardless of the individual user's own headroom.
    """
    if platform_daily_spend_usd >= platform_daily_cap_usd:
        raise CapExceeded("platform_daily")
    if user_daily_spend_usd >= user_daily_cap_usd:
        raise CapExceeded("user_daily")
    if session_spend_usd >= session_cap_usd:
        raise CapExceeded("session")
