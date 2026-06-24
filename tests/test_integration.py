"""Integration-style test: in-memory SQLite + mocked LLM, full conversation flow."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from openai import BadRequestError

from app.application.ports import LLMResult
from app.main import app as main_app
from tests.conftest import TEST_USER


def _make_llm_result(
    text: str,
    model: str = "gpt-4.1-mini",
    ttfb_ms: int = 50,
    total_ms: int = 100,
) -> LLMResult:
    return LLMResult(text=text, model=model, ttfb_ms=ttfb_ms, total_ms=total_ms)


@pytest.fixture
def mock_llm():
    """Mock LLM that returns deterministic replies."""
    mock = MagicMock()
    mock.complete.side_effect = [
        _make_llm_result("Hello back!"),
        _make_llm_result("Second reply."),
    ]
    return mock


@pytest.fixture
def client_with_mock_llm(mock_llm):
    """Override get_llm; use main app so lifespan and in-memory DB are used."""
    from app.api import routes as api_routes

    main_app.dependency_overrides[api_routes.get_llm] = lambda: mock_llm
    with TestClient(main_app) as c:
        yield c
    main_app.dependency_overrides.clear()


def test_integration_create_then_append_turn(client_with_mock_llm, mock_llm) -> None:
    """Full flow: create conversation, append turn; assert response shape and second call."""
    # Create conversation (first turn)
    r1 = client_with_mock_llm.post(
        f"/u/{TEST_USER}/conversations",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert r1.status_code == 200
    data1 = r1.json()
    cid = data1["conversation_id"]
    assert data1["assistant_message"] == "Hello back!"
    assert "timings" in data1

    # Append second turn
    r2 = client_with_mock_llm.post(
        f"/u/{TEST_USER}/conversations/{cid}",
        json={"messages": [{"role": "user", "content": "Second"}]},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["conversation_id"] == cid
    assert data2["assistant_message"] == "Second reply."

    # LLM was called twice: once for create, once for append.
    assert mock_llm.complete.call_count == 2
    # Second call receives full history: user + assistant from first turn, then new user.
    second_call_messages = mock_llm.complete.call_args_list[1][0][1]
    roles = [m["role"] for m in second_call_messages]
    contents = [m["content"] for m in second_call_messages]
    assert roles == ["user", "assistant", "user"]
    assert contents == ["Hi", "Hello back!", "Second"]


def _make_fake_openai_response(text: str, model: str = "gpt-4.1-mini-2025-04-14"):
    """Helper to build a fake OpenAI Responses API object for adapter tests."""
    block = MagicMock(type="output_text", text=text)
    item = MagicMock(type="message", content=[block])
    return MagicMock(output=[item], model=model)


@pytest.fixture
def client_with_openai_adapter_stub():
    """
    Test client that uses the real OpenAILLMAdapter wired through FastAPI deps,
    but with the underlying OpenAI client stubbed so no real network calls occur.
    """
    from unittest.mock import patch

    from app.api import routes as api_routes
    from app.infra.llm_openai import OpenAILLMAdapter
    from app.settings import Settings

    settings = Settings()

    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.responses.create.side_effect = [
            _make_fake_openai_response("Hello Mika! How can I assist you today?"),
            _make_fake_openai_response("Your name is Mika."),
        ]
        mock_openai_class.return_value = mock_client

        adapter = OpenAILLMAdapter(settings)
        main_app.dependency_overrides[api_routes.get_llm] = lambda: adapter

        with TestClient(main_app) as c:
            yield c, mock_client

    main_app.dependency_overrides.clear()


def test_create_then_append_turn_reproduces_mika_flow(
    client_with_openai_adapter_stub,
) -> None:
    """
    Reproduce the curl sequence from the bug report:

    1. POST /u/{user_id}/conversations with prompt_slug="default" and "Hi my name is Mika"
    2. POST /u/{user_id}/conversations/{conversation_id} asking "What is my name?"
    """
    client, mock_client = client_with_openai_adapter_stub

    # First turn
    r1 = client.post(
        f"/u/{TEST_USER}/conversations",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "Hi my name is Mika"}],
        },
    )
    assert r1.status_code == 200
    data1 = r1.json()
    cid = data1["conversation_id"]
    assert data1["assistant_message"] == "Hello Mika! How can I assist you today?"

    # Second turn
    r2 = client.post(
        f"/u/{TEST_USER}/conversations/{cid}",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "What is my name?"}],
        },
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["conversation_id"] == cid
    assert data2["assistant_message"] == "Your name is Mika."
    assert "timings" in data2

    assert mock_client.responses.create.call_count == 2


@pytest.fixture
def client_with_bad_request_error_on_append():
    """
    Test client where the first OpenAI call succeeds and the second raises BadRequestError.
    """
    from unittest.mock import patch

    from app.api import routes as api_routes
    from app.infra.llm_openai import OpenAILLMAdapter
    from app.settings import Settings

    settings = Settings()

    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()

        ok_response = _make_fake_openai_response("Hello Mika! How can I assist you today?")

        bad_request = BadRequestError(
            "bad request",
            response=MagicMock(),
            body={
                "error": {
                    "message": "Invalid value: 'input_text'. Supported values are: 'output_text' and 'refusal'.",
                    "type": "invalid_request_error",
                    "param": "input[1].content[0]",
                    "code": "invalid_value",
                }
            },
        )

        mock_client.responses.create.side_effect = [ok_response, bad_request]
        mock_openai_class.return_value = mock_client

        adapter = OpenAILLMAdapter(settings)
        main_app.dependency_overrides[api_routes.get_llm] = lambda: adapter

        with TestClient(main_app) as c:
            yield c

    main_app.dependency_overrides.clear()


def test_append_turn_maps_openai_bad_request_to_http_error(
    client_with_bad_request_error_on_append,
) -> None:
    """
    When OpenAI returns BadRequestError (400) for an append turn, the service
    should surface a mapped HTTP error (502) rather than 500 Internal Server Error.
    """
    client = client_with_bad_request_error_on_append

    r1 = client.post(
        f"/u/{TEST_USER}/conversations",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "Hi my name is Mika"}],
        },
    )
    assert r1.status_code == 200
    cid = r1.json()["conversation_id"]

    r2 = client.post(
        f"/u/{TEST_USER}/conversations/{cid}",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "What is my name?"}],
        },
    )

    assert r2.status_code == 502
    body = r2.json()
    assert body["detail"] == "Upstream OpenAI API error."
