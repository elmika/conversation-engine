"""Service-level tests: code-owned time-over selects the closure prompt.

A subsequent (core) turn resolves to CORE while there's time left, and to
CLOSURE once the session's time is up — decided in code from the stored
session length, no model involved. In-memory repo + fakes, no network.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.ports import StreamEvent
from app.application.services import ConversationService
from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork
from app.learning.flow_orchestrator import LearningFlowOrchestrator

TEST_USER = "test-user"
CID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"  # valid UUID (append_and_stream validates format)

# Prompts without {{section}} tags so rendering needs no section files.
_PROMPTS = {
    "course-session-core": {
        "slug": "course-session-core",
        "system_prompt": "CORE PROMPT",
        "model": None,
        "name": "core",
    },
    "course-session-closure": {
        "slug": "course-session-closure",
        "system_prompt": "CLOSURE PROMPT",
        "model": None,
        "name": "closure",
    },
}


class FakePromptRepo:
    def get_prompt(self, slug):
        return _PROMPTS.get(slug)

    def get_prompt_or_default(self, slug, default):
        return _PROMPTS.get(slug) or _PROMPTS.get(default)


class FakeLLM:
    def stream(self, instructions, messages, model=None):
        yield StreamEvent(type="final", text="ok", model=model or "fake", ttfb_ms=0, total_ms=0)

    def complete(self, *args, **kwargs):  # used by maybe_update_session_length; harmless here
        from app.application.ports import LLMResult

        return LLMResult(
            text="NONE", model="fake", ttfb_ms=0, total_ms=0, input_tokens=0, output_tokens=0
        )


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


def _service(uow_factory) -> ConversationService:
    llm = FakeLLM()
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


def _seed_course_session(uow_factory, session_length_minutes, objective_met=False) -> None:
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID,
            user_id=TEST_USER,
            prompt_slug="course-session-init",
            session_length_minutes=session_length_minutes,
        )
        uow.repo.append_message(CID, "assistant", "opening message")
        if objective_met:
            uow.repo.set_objective_met(CID, TEST_USER)
        uow.commit()


def _used_slug_for_next_turn(uow_factory) -> str:
    svc = _service(uow_factory)
    _, _, used_slug, _, _ = svc.append_and_stream(CID, [{"role": "user", "content": "go on"}])
    return used_slug


def test_core_prompt_while_time_remains(uow_factory):
    _seed_course_session(uow_factory, session_length_minutes=120)  # just started, far from limit
    assert _used_slug_for_next_turn(uow_factory) == "course-session-core"


def test_closure_prompt_once_time_is_up(uow_factory):
    # length <= wind-down buffer → the session is in its closing window immediately.
    _seed_course_session(uow_factory, session_length_minutes=1)
    assert _used_slug_for_next_turn(uow_factory) == "course-session-closure"


def test_no_session_length_never_closes(uow_factory):
    # session_length None (e.g. legacy/flat) → time-over check skipped → stays CORE.
    _seed_course_session(uow_factory, session_length_minutes=None)
    assert _used_slug_for_next_turn(uow_factory) == "course-session-core"


def test_objective_met_closes_even_within_time(uow_factory):
    # Plenty of time left, but the objective guard has latched completion → CLOSURE.
    _seed_course_session(uow_factory, session_length_minutes=120, objective_met=True)
    assert _used_slug_for_next_turn(uow_factory) == "course-session-closure"
