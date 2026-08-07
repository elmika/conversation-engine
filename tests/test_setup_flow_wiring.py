"""Integration test: a setup conversation hits TWO different prompts.

Framing turns (name, industry, motivation, session length) use the FRAMING
prompt (user-profile-collection); the turn that answers the 4th question — and
every turn after — uses the OUTLINE prompt (course-outline-proposal). This
proves the phase→prompt mapping is wired through the service, not just
unit-tested in isolation (see test_setup_flow.py).

Uses the non-streaming routes (create_and_chat → append_and_chat) with a mocked
LLM, so we can inspect exactly which system prompt each turn received.

Note on turn counting: `create_and_chat` (the plain `/conversations` route used
here to open the conversation) persists whatever opening message it's given as
a real user turn. Production opens setup conversations via
`/conversations/init-stream` → `create_and_stream_init`, which uses a HIDDEN,
non-persisted trigger instead — so in the live app the opening turn does not
count towards the 4-question framing total. This test accounts for that
difference: the opening call here already counts as user turn #1, so only 3
more answers (not 4) are needed to cross FRAMING_TURNS.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports import LLMResult
from app.main import app as main_app
from tests.conftest import TEST_USER


@pytest.fixture
def mock_llm():
    mock = MagicMock()
    mock.complete.side_effect = [
        LLMResult(text="welcome, what's your name?", model="gpt-4.1", ttfb_ms=10, total_ms=50),
        LLMResult(text="and your industry?", model="gpt-4.1", ttfb_ms=10, total_ms=50),
        LLMResult(text="what's your motivation?", model="gpt-4.1", ttfb_ms=10, total_ms=50),
        LLMResult(
            text="here's your course outline...", model="gpt-5.6-luna", ttfb_ms=10, total_ms=50
        ),
        LLMResult(
            text="sure, here's the revised outline...", model="gpt-5.6-luna", ttfb_ms=10, total_ms=50
        ),
    ]
    return mock


@pytest.fixture
def client(mock_llm):
    from app.api import routes as api_routes

    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def test_framing_turns_use_profile_prompt_then_switches_to_outline_prompt(
    client, mock_llm
) -> None:
    # Call 1 (index 0): opens the flow. Persists "start" as user turn #1 in this
    # harness (see module docstring) — always FRAMING regardless of counting,
    # since create_and_chat resolves the prompt directly from prompt_slug.
    r1 = client.post(
        f"/u/{TEST_USER}/conversations",
        json={
            "messages": [{"role": "user", "content": "start"}],
            "prompt_slug": "user-profile-collection",
        },
    )
    assert r1.status_code == 200, r1.json()
    cid = r1.json()["conversation_id"]

    # Calls 2-3 (index 1-2): user turns #2 and #3 — still below FRAMING_TURNS (4).
    for answer in ("I'm Alex", "backend engineer in fintech"):
        r = client.post(
            f"/u/{TEST_USER}/conversations/{cid}",
            json={"messages": [{"role": "user", "content": answer}]},
        )
        assert r.status_code == 200, r.json()

    # Call 4 (index 3): user turn #4 — crosses FRAMING_TURNS, switches to OUTLINE.
    r4 = client.post(
        f"/u/{TEST_USER}/conversations/{cid}",
        json={
            "messages": [{"role": "user", "content": "want to learn pandas, 20-30 min sessions"}]
        },
    )
    assert r4.status_code == 200, r4.json()

    # Call 5 (index 4): a follow-up refinement turn — must stay on OUTLINE.
    r5 = client.post(
        f"/u/{TEST_USER}/conversations/{cid}",
        json={"messages": [{"role": "user", "content": "can you make module 2 more advanced?"}]},
    )
    assert r5.status_code == 200, r5.json()

    instructions = [call[0][0] for call in mock_llm.complete.call_args_list]
    assert len(instructions) == 5

    # Calls 1-3 = FRAMING prompt.
    for i in range(3):
        assert "already asked the learner four framing questions" not in instructions[i], (
            f"call {i + 1} unexpectedly used the OUTLINE prompt"
        )
        assert "EXACTLY these four questions" in instructions[i]

    # Calls 4-5 = OUTLINE prompt.
    for i in (3, 4):
        assert "already asked the learner four framing questions" in instructions[i], (
            f"call {i + 1} unexpectedly used the FRAMING prompt"
        )
        assert "EXACTLY these four questions" not in instructions[i]
