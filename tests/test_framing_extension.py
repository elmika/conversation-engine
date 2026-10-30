"""Tests for maybe_extend_framing_turns: a learner reply that doesn't answer the
pending setup question shouldn't silently consume a framing-turn slot.

Reproduces the real failure (2026-09-17): name -> work -> "What skill are you
talking about?" (a clarifying question, not an answer) -> the real motivation
answer lands on turn 4 and the flow jumps straight to OUTLINE, skipping the
session-length question entirely. In-memory repo + fakes, no network.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.ports import LLMResult
from app.application.services import ConversationService
from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork
from app.learning.flow_orchestrator import LearningFlowOrchestrator
from app.learning.setup_flow import FRAMING_TURNS

TEST_USER = "test-user"
CID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

_PROMPTS = {
    "framing-answer-check": {
        "slug": "framing-answer-check",
        "system_prompt": "ANSWERED?",
        "model": "gpt-5.4-nano",
        "name": "framing-answer-check",
    },
}


class FakePromptRepo:
    def get_prompt(self, slug):
        return _PROMPTS.get(slug)

    def get_prompt_or_default(self, slug, default):
        return _PROMPTS.get(slug) or _PROMPTS.get(default)


class FakeLLM:
    def __init__(self, complete_text: str = "YES") -> None:
        self.complete_text = complete_text
        self.complete_calls: list = []

    def complete(self, instructions, messages, model=None):
        self.complete_calls.append((instructions, messages, model))
        return LLMResult(
            text=self.complete_text,
            model="fake",
            ttfb_ms=0,
            total_ms=0,
            input_tokens=0,
            output_tokens=0,
        )

    def stream(self, *a, **k):
        yield from ()


class _NullResolver:
    def resolve(self, tag):
        return None


@pytest.fixture
def uow_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return lambda: SQLAlchemyUnitOfWork(SessionLocal())


def _service(uow_factory, llm: FakeLLM) -> ConversationService:
    prompt_repo = FakePromptRepo()
    slot_resolver = _NullResolver()
    return ConversationService(
        uow_factory=uow_factory,
        llm=llm,
        prompt_repo=prompt_repo,
        default_prompt_slug="user-profile-collection",
        default_model="gpt-4.1",
        slot_resolver=slot_resolver,
        flow=LearningFlowOrchestrator(uow_factory, llm, prompt_repo, slot_resolver, TEST_USER),
        user_id=TEST_USER,
    )


def _seed(uow_factory, *, exchanges: list[tuple[str, str]]) -> None:
    """exchanges: [(tutor question, learner reply), ...] in order."""
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID, user_id=TEST_USER, prompt_slug="user-profile-collection"
        )
        for question, answer in exchanges:
            uow.repo.append_message(CID, "assistant", question)
            uow.repo.append_message(CID, "user", answer)
        uow.commit()


def _conv(uow_factory) -> dict:
    with uow_factory() as uow:
        return uow.repo.get_conversation(CID, TEST_USER)


def test_extends_framing_when_reply_did_not_answer(uow_factory):
    _seed(
        uow_factory,
        exchanges=[
            ("What's your name?", "I'm Mik"),
            ("What do you do for work?", "software engineer and entrepreneur"),
            ("What made you want to explore this skill?", "What skill are you talking about?"),
        ],
    )
    llm = FakeLLM(complete_text="NO")  # the model judges: this reply didn't answer
    _service(uow_factory, llm).maybe_extend_framing_turns(CID)

    assert _conv(uow_factory)["framing_turns_required"] == FRAMING_TURNS + 1
    assert len(llm.complete_calls) == 1


def test_no_extension_when_reply_answered_normally(uow_factory):
    _seed(
        uow_factory,
        exchanges=[
            ("What's your name?", "I'm Mik"),
            ("What do you do for work?", "software engineer and entrepreneur"),
            (
                "What made you want to explore this skill?",
                "I want to get sharper on AI product design.",
            ),
        ],
    )
    llm = FakeLLM(complete_text="YES")
    _service(uow_factory, llm).maybe_extend_framing_turns(CID)

    assert _conv(uow_factory)["framing_turns_required"] is None  # unchanged
    assert len(llm.complete_calls) == 1


def test_skips_once_already_past_framing(uow_factory):
    # 4 exchanges already -> this turn already crossed the (default) FRAMING_TURNS
    # threshold; too late to correct via this hook.
    _seed(
        uow_factory,
        exchanges=[
            ("What's your name?", "I'm Mik"),
            ("What do you do for work?", "engineer"),
            ("What made you want to explore this skill?", "career growth"),
            ("How long do you usually have for a session?", "20 minutes"),
        ],
    )
    llm = FakeLLM(complete_text="NO")  # would extend if called — proves the skip, not the model
    _service(uow_factory, llm).maybe_extend_framing_turns(CID)

    assert _conv(uow_factory)["framing_turns_required"] is None
    assert llm.complete_calls == []


def test_skips_non_setup_flow_conversations(uow_factory):
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID, user_id=TEST_USER, prompt_slug="course-session-init"
        )
        uow.repo.append_message(CID, "assistant", "opening")
        uow.repo.append_message(CID, "user", "some reply")
        uow.commit()

    llm = FakeLLM(complete_text="NO")
    _service(uow_factory, llm).maybe_extend_framing_turns(CID)
    assert llm.complete_calls == []


def test_synchronous_check_catches_a_detour_landing_on_the_threshold_turn_itself(uow_factory):
    """The exact 'Bubi' repro (2026-09-17): unlike test_the_reported_repro_end_to_end
    above (where the clarifying question lands on turn 3, strictly before the
    threshold), here it lands ON turn 4 itself — the threshold-crossing turn.
    maybe_extend_framing_turns can never see this case (by the time it would run,
    OUTLINE has already fired for this exact turn) — only the synchronous check
    inside resolve_effective_prompt can catch it, in the same turn."""
    _seed(
        uow_factory,
        exchanges=[
            ("What's your name?", "Bubi"),
            ("What do you do for work?", "travel agent, organise hikes"),
            ("What made you want to explore this skill?", "career growth"),
        ],
    )
    llm = FakeLLM(complete_text="NO")  # "What skill are you referring to?" doesn't answer
    prompt_repo = FakePromptRepo()
    slot_resolver = _NullResolver()
    flow = LearningFlowOrchestrator(uow_factory, llm, prompt_repo, slot_resolver, TEST_USER)

    with uow_factory() as uow:
        conv_meta = uow.repo.get_conversation(CID, TEST_USER)
        history = uow.repo.get_messages(CID, TEST_USER)
        pending = [{"role": "user", "content": "What skill are you referring to?"}]
        effective_slug = flow.resolve_effective_prompt(
            conv_meta["prompt_slug"], conv_meta, None, history, pending, uow=uow
        )
        uow.commit()

    assert effective_slug == "user-profile-collection"  # stayed on FRAMING, not OUTLINE
    assert _conv(uow_factory)["framing_turns_required"] == FRAMING_TURNS + 1


def test_synchronous_check_does_not_fire_on_a_legitimate_later_outline_turn(uow_factory):
    """Once OUTLINE has legitimately started, a normal refinement reply must
    never be re-routed through the threshold check (that would wrongly re-lock
    framing on every later turn)."""
    _seed(
        uow_factory,
        exchanges=[
            ("What's your name?", "Bubi"),
            ("What do you do for work?", "travel agent"),
            ("What made you want to explore this skill?", "career growth"),
            ("How long do you usually have for a session?", "20 minutes"),
        ],
    )
    llm = FakeLLM(complete_text="NO")  # would (wrongly) extend framing if ever called
    prompt_repo = FakePromptRepo()
    slot_resolver = _NullResolver()
    flow = LearningFlowOrchestrator(uow_factory, llm, prompt_repo, slot_resolver, TEST_USER)

    with uow_factory() as uow:
        conv_meta = uow.repo.get_conversation(CID, TEST_USER)
        history = uow.repo.get_messages(CID, TEST_USER)
        pending = [{"role": "user", "content": "can you make module 2 more advanced?"}]
        effective_slug = flow.resolve_effective_prompt(
            conv_meta["prompt_slug"], conv_meta, None, history, pending, uow=uow
        )
        uow.commit()

    assert effective_slug == "course-outline-proposal"
    assert _conv(uow_factory)["framing_turns_required"] is None  # never touched
    assert llm.complete_calls == []  # threshold check never re-fires on later turns


def test_the_reported_repro_end_to_end(uow_factory):
    """The exact real-world sequence: clarifying question on turn 3 pushes the
    real motivation answer to turn 4 — without the fix, that turn would cross
    FRAMING_TURNS and jump straight to OUTLINE, skipping session length."""
    _seed(
        uow_factory,
        exchanges=[
            ("What's your name?", "I'm Mik"),
            ("What do you do for work?", "software engineer and entrepreneur, building my project"),
            ("What made you want to explore this skill?", "What skill are you talking about?"),
        ],
    )
    llm = FakeLLM(complete_text="NO")
    svc = _service(uow_factory, llm)
    svc.maybe_extend_framing_turns(CID)
    required = _conv(uow_factory)["framing_turns_required"]
    assert required == FRAMING_TURNS + 1

    # The real motivation answer now arrives as turn 4 — with the extended
    # requirement (5), setup_phase_for_turn must still say FRAMING.
    from app.learning.setup_flow import SetupPhase, setup_phase_for_turn

    assert setup_phase_for_turn(4, required) is SetupPhase.FRAMING
    assert setup_phase_for_turn(5, required) is SetupPhase.OUTLINE
