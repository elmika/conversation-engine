"""Service-level tests for in-chat session-length capture (maybe_update_session_length).

Uses a real in-memory repo with fake LLM + prompt repo, so the orchestration
(gate → pre-filter → extract → validate → persist) is exercised without network.
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

TEST_USER = "test-user"
CID = "conv-1"


class FakePromptRepo:
    def __init__(self, prompts: dict) -> None:
        self._prompts = prompts

    def get_prompt(self, slug: str):
        return self._prompts.get(slug)


class RecordingLLM:
    """Fake LLM that records .complete() calls and returns a fixed text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list = []

    def complete(self, instructions, messages, model=None) -> LLMResult:
        self.calls.append((instructions, messages, model))
        return LLMResult(
            text=self.text,
            model=model or "fake",
            ttfb_ms=0,
            total_ms=0,
            input_tokens=0,
            output_tokens=0,
        )

    def stream(self, *args, **kwargs):  # unused here
        yield from ()


class _NullResolver:
    def resolve(self, tag: str):
        return None


@pytest.fixture
def uow_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def factory():
        return SQLAlchemyUnitOfWork(SessionLocal())

    return factory


def _service(uow_factory, llm) -> ConversationService:
    prompt_repo = FakePromptRepo(
        {"session-length-extraction": {"system_prompt": "extract", "model": "gpt-5.4-nano"}}
    )
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


def _seed_conversation(uow_factory, session_length, question, answer) -> None:
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID,
            user_id=TEST_USER,
            prompt_slug="course-session-init",
            session_length_minutes=session_length,
        )
        if question is not None:
            uow.repo.append_message(CID, "assistant", question)
        if answer is not None:
            uow.repo.append_message(CID, "user", answer)
        uow.commit()


def _stored_length(uow_factory) -> int | None:
    with uow_factory() as uow:
        return uow.repo.get_conversation(CID, TEST_USER)["session_length_minutes"]


def test_explicit_change_is_extracted_and_persisted(uow_factory):
    _seed_conversation(
        uow_factory, 15, "I've got you down for 15 min — work today?", "let's do 30 today"
    )
    llm = RecordingLLM("30")
    _service(uow_factory, llm).maybe_update_session_length(CID)
    assert _stored_length(uow_factory) == 30
    assert len(llm.calls) == 1  # extraction ran


def test_no_duration_hint_skips_the_model_call(uow_factory):
    _seed_conversation(uow_factory, 15, "What does this function do?", "it loops over the list")
    llm = RecordingLLM("30")
    _service(uow_factory, llm).maybe_update_session_length(CID)
    assert _stored_length(uow_factory) == 15  # unchanged
    assert llm.calls == []  # pre-filter short-circuited — no LLM call


def test_model_says_none_leaves_length_unchanged(uow_factory):
    _seed_conversation(uow_factory, 15, "anything else?", "I spent 45 minutes debugging yesterday")
    llm = RecordingLLM("NONE")
    _service(uow_factory, llm).maybe_update_session_length(CID)
    assert _stored_length(uow_factory) == 15
    assert len(llm.calls) == 1  # filter passed (mentions "45 minutes"), model rejected intent


def test_nonsensical_value_is_ignored(uow_factory):
    _seed_conversation(uow_factory, 15, "how long today?", "let's go for 11 hours")
    llm = RecordingLLM("660")  # 11 hours — out of sane range
    _service(uow_factory, llm).maybe_update_session_length(CID)
    assert _stored_length(uow_factory) == 15  # unchanged


def test_non_lesson_conversation_is_skipped(uow_factory):
    # session_length None = flat prompt (e.g. setup) → never tracked.
    _seed_conversation(uow_factory, None, "tell me about yourself", "I have 30 minutes")
    llm = RecordingLLM("30")
    _service(uow_factory, llm).maybe_update_session_length(CID)
    assert _stored_length(uow_factory) is None
    assert llm.calls == []
