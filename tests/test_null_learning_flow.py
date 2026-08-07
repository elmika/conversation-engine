"""Proves NullLearningFlow actually lets ConversationService run standalone.

CLAUDE.md's "Layer model" section claims NullLearningFlow "prov[es]
ConversationService can run with zero Layer 2 knowledge bound." Nothing
wired it in (routes.py always uses the real LearningFlowOrchestrator), so
that claim was undemonstrated. This test constructs the service with
NullLearningFlow directly and asserts flat, phase-less behavior: no prompt
switching, no session-length seeding, and no LLM calls from the background
hooks. In-memory repo + fakes, no network.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.ports import LLMResult, NullLearningFlow, StreamEvent
from app.application.services import ConversationService
from app.infra.persistence.db import Base
from app.infra.persistence.models import Conversation, Message, Run  # noqa: F401 - register models
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork

TEST_USER = "test-user"
CID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"  # valid UUID (append_and_stream validates format)

_PROMPTS = {
    "default": {
        "slug": "default",
        "system_prompt": "DEFAULT PROMPT",
        "model": None,
        "name": "default",
    },
}


class FakePromptRepo:
    def get_prompt(self, slug):
        return _PROMPTS.get(slug)

    def get_prompt_or_default(self, slug, default):
        return _PROMPTS.get(slug) or _PROMPTS.get(default)


class FakeLLM:
    def __init__(self) -> None:
        self.complete_calls: list = []

    def stream(self, instructions, messages, model=None):
        yield StreamEvent(type="final", text="ok", model=model or "fake", ttfb_ms=0, total_ms=0)

    def complete(self, instructions, messages, model=None) -> LLMResult:
        self.complete_calls.append((instructions, messages, model))
        return LLMResult(
            text="YES",
            model=model or "fake",
            ttfb_ms=0,
            total_ms=0,
            input_tokens=0,
            output_tokens=0,
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


def _service(uow_factory, llm) -> ConversationService:
    return ConversationService(
        uow_factory=uow_factory,
        llm=llm,
        prompt_repo=FakePromptRepo(),
        default_prompt_slug="default",
        default_model="gpt-4.1",
        slot_resolver=_NullResolver(),
        flow=NullLearningFlow(),
        user_id=TEST_USER,
    )


def test_create_and_stream_init_seeds_no_session_length(uow_factory):
    llm = FakeLLM()
    svc = _service(uow_factory, llm)
    conversation_id, events, used_slug, _, uow = svc.create_and_stream_init(prompt_slug="default")
    list(events)  # drain the stream
    with uow:
        conv = uow.repo.get_conversation(conversation_id, TEST_USER)
    assert used_slug == "default"
    assert conv["session_length_minutes"] is None


def test_append_and_stream_keeps_prompt_slug_unchanged(uow_factory):
    llm = FakeLLM()
    svc = _service(uow_factory, llm)
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID, user_id=TEST_USER, prompt_slug="default", session_length_minutes=None
        )
        uow.repo.append_message(CID, "assistant", "opening message")
        uow.commit()

    _, events, used_slug, _, _ = svc.append_and_stream(
        CID, [{"role": "user", "content": "let's do 30 minutes"}]
    )
    list(events)  # drain the stream

    assert used_slug == "default"  # no phase/closure branching for a flat prompt


def test_background_hooks_never_call_the_llm(uow_factory):
    llm = FakeLLM()
    svc = _service(uow_factory, llm)
    with uow_factory() as uow:
        uow.repo.create_conversation_with_id(
            CID, user_id=TEST_USER, prompt_slug="default", session_length_minutes=None
        )
        uow.repo.append_message(CID, "assistant", "opening")
        uow.repo.append_message(CID, "user", "I've got 45 minutes today")
        uow.commit()

    svc.maybe_update_session_length(CID)
    svc.maybe_flag_objective_complete(CID)

    assert (
        llm.complete_calls == []
    )  # NullLearningFlow's hooks are no-ops, unlike the real orchestrator
