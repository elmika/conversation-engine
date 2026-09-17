"""Tests for the objective guard: pure verdict parsing + service orchestration.

In-memory repo + fakes, no network.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.ports import LLMResult
from app.application.services import ConversationService
from app.learning.flow_orchestrator import LearningFlowOrchestrator
from app.learning.objective_guard import (
    OBJECTIVE_GUARD_MIN_TURNS,
    objective_guard_min_turns,
    parse_objective_result,
)
from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork

TEST_USER = "test-user"
CID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


class TestParseObjectiveResult:
    @pytest.mark.parametrize("raw", ["YES", "yes", "Yes", "YES.", "YES, clearly met"])
    def test_yes_is_true(self, raw):
        assert parse_objective_result(raw) is True

    @pytest.mark.parametrize("raw", ["NO", "no", "Not yet", "unsure", "", "  ", None])
    def test_anything_else_is_false(self, raw):
        assert parse_objective_result(raw) is False


_PROMPTS = {
    "lesson-objective-complete": {"slug": "lesson-objective-complete", "system_prompt": "GUARD", "model": "gpt-5.4-nano", "name": "guard"},
}


class FakePromptRepo:
    def get_prompt(self, slug):
        return _PROMPTS.get(slug)

    def get_prompt_or_default(self, slug, default):
        return _PROMPTS.get(slug) or _PROMPTS.get(default)


class RecordingLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list = []

    def complete(self, instructions, messages, model=None) -> LLMResult:
        self.calls.append((instructions, messages, model))
        return LLMResult(text=self.text, model=model or "fake", ttfb_ms=0, total_ms=0, input_tokens=0, output_tokens=0)

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


def _service(uow_factory, llm):
    prompt_repo = FakePromptRepo()
    slot_resolver = _NullResolver()
    return ConversationService(
        uow_factory=uow_factory,
        llm=llm,
        prompt_repo=prompt_repo,
        default_prompt_slug="course-session-init",
        default_model="gpt-4.1",
        slot_resolver=slot_resolver,
        flow=LearningFlowOrchestrator(uow_factory, llm, prompt_repo, slot_resolver, TEST_USER),
        user_id=TEST_USER,
    )


def _seed(uow_factory, *, user_turns: int, session_length=8) -> None:
    # session_length=8 keeps objective_guard_min_turns() at the OBJECTIVE_GUARD_MIN_TURNS
    # floor (8 // MINUTES_PER_EXCHANGE(2) == 4), so existing fixed-turn-count tests below
    # don't need to know about the dynamic scaling — see TestObjectiveGuardMinTurns for that.
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID, user_id=TEST_USER, prompt_slug="course-session-init", session_length_minutes=session_length
        )
        uow.repo.append_message(CID, "assistant", "opening")
        for i in range(user_turns):
            uow.repo.append_message(CID, "user", f"turn {i}")
            uow.repo.append_message(CID, "assistant", f"reply {i}")
        uow.commit()


def _objective_met(uow_factory) -> bool:
    with uow_factory() as uow:
        return uow.repo.get_conversation(CID, TEST_USER)["objective_met"]


def test_guard_latches_objective_when_yes(uow_factory):
    _seed(uow_factory, user_turns=OBJECTIVE_GUARD_MIN_TURNS)
    llm = RecordingLLM("YES")
    _service(uow_factory, llm).maybe_flag_objective_complete(CID)
    assert _objective_met(uow_factory) is True
    assert len(llm.calls) == 1


def test_guard_no_keeps_objective_unmet(uow_factory):
    _seed(uow_factory, user_turns=OBJECTIVE_GUARD_MIN_TURNS)
    llm = RecordingLLM("NO")
    _service(uow_factory, llm).maybe_flag_objective_complete(CID)
    assert _objective_met(uow_factory) is False
    assert len(llm.calls) == 1


def test_guard_skipped_before_min_turns(uow_factory):
    _seed(uow_factory, user_turns=OBJECTIVE_GUARD_MIN_TURNS - 1)
    llm = RecordingLLM("YES")
    _service(uow_factory, llm).maybe_flag_objective_complete(CID)
    assert _objective_met(uow_factory) is False
    assert llm.calls == []  # too early — no guard call


def test_guard_skipped_for_non_lesson_conversation(uow_factory):
    _seed(uow_factory, user_turns=OBJECTIVE_GUARD_MIN_TURNS, session_length=None)
    llm = RecordingLLM("YES")
    _service(uow_factory, llm).maybe_flag_objective_complete(CID)
    assert llm.calls == []


class TestObjectiveGuardMinTurns:
    """A 30-minute session shouldn't be eligible for closure at the same turn
    count as a 10-minute one — the floor scales with the planned length."""

    def test_floors_at_the_fixed_minimum_for_short_or_default_sessions(self):
        assert objective_guard_min_turns(None) == OBJECTIVE_GUARD_MIN_TURNS
        assert objective_guard_min_turns(4) == OBJECTIVE_GUARD_MIN_TURNS  # below floor

    def test_scales_with_session_length(self):
        assert objective_guard_min_turns(30) == 15
        assert objective_guard_min_turns(60) == 30


def _seed_with_id(uow_factory, cid: str, *, user_turns: int, session_length: int) -> None:
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            cid, user_id=TEST_USER, prompt_slug="course-session-init", session_length_minutes=session_length
        )
        uow.repo.append_message(cid, "assistant", "opening")
        for i in range(user_turns):
            uow.repo.append_message(cid, "user", f"turn {i}")
            uow.repo.append_message(cid, "assistant", f"reply {i}")
        uow.commit()


def test_guard_skipped_before_scaled_min_turns_on_longer_session(uow_factory):
    # 30-minute session -> min_turns == 15; 4 turns (the old fixed floor) is still too early.
    cid = "1a1a1a1a-1111-4111-8111-111111111111"
    _seed_with_id(uow_factory, cid, user_turns=OBJECTIVE_GUARD_MIN_TURNS, session_length=30)
    llm = RecordingLLM("YES")
    _service(uow_factory, llm).maybe_flag_objective_complete(cid)
    assert llm.calls == []


def test_guard_fires_once_scaled_min_turns_reached_on_longer_session(uow_factory):
    cid = "2b2b2b2b-2222-4222-8222-222222222222"
    _seed_with_id(uow_factory, cid, user_turns=15, session_length=30)
    llm = RecordingLLM("YES")
    _service(uow_factory, llm).maybe_flag_objective_complete(cid)
    assert len(llm.calls) == 1
    with uow_factory() as uow:
        assert uow.repo.get_conversation(cid, TEST_USER)["objective_met"] is True
