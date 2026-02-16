"""Integration-style test: in-memory SQLite + mocked LLM, full conversation flow."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from openai import BadRequestError

from app.application.ports import LLMResult
from app.main import app as main_app


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
        "/conversations",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert r1.status_code == 200
    data1 = r1.json()
    cid = data1["conversation_id"]
    assert data1["assistant_message"] == "Hello back!"
    assert "timings" in data1

    # Append second turn
    r2 = client_with_mock_llm.post(
        f"/conversations/{cid}",
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

    This exercises the same path as your curl example hitting /conversations
    and then /conversations/{conversation_id}.
    """
    from unittest.mock import patch

    from app.api import routes as api_routes
    from app.infra.llm_openai import OpenAILLMAdapter
    from app.settings import Settings

    # Use a fresh Settings instance for the adapter instead of relying on
    # app.state, which is only initialised inside the FastAPI lifespan.
    settings = Settings()

    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        # First call: create_conversation
        # Second call: append_conversation_turn
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

    1. POST /conversations with prompt_slug="default" and "Hi my name is Mika"
    2. POST /conversations/{conversation_id} asking "What is my name?"

    The expected behaviour is 200 OK for both calls and a valid assistant_message
    on the second response (no internal server error).
    """
    client, mock_client = client_with_openai_adapter_stub

    # First turn – matches your first curl.
    r1 = client.post(
        "/conversations",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "Hi my name is Mika"}],
        },
    )
    assert r1.status_code == 200
    data1 = r1.json()
    cid = data1["conversation_id"]
    assert data1["assistant_message"] == "Hello Mika! How can I assist you today?"

    # Second turn – matches your second curl.
    r2 = client.post(
        f"/conversations/{cid}",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "What is my name?"}],
        },
    )
    # This is where your running app currently returns 500.
    # The test encodes the *expected* correct behaviour (no internal error).
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["conversation_id"] == cid
    assert data2["assistant_message"] == "Your name is Mika."
    assert "timings" in data2

    # Sanity-check that the OpenAI client was invoked twice.
    assert mock_client.responses.create.call_count == 2


@pytest.fixture
def client_with_bad_request_error_on_append():
    """
    Test client where the first OpenAI call succeeds and the second (append turn)
    raises BadRequestError, simulating an invalid Responses API payload.

    This documents the expected HTTP-level behaviour: the service should map the
    OpenAI error to a 5xx HTTPException (via _map_openai_error) instead of
    returning a generic 500 "Internal server error".
    """
    from unittest.mock import patch

    from app.api import routes as api_routes
    from app.infra.llm_openai import OpenAILLMAdapter
    from app.settings import Settings

    settings = Settings()

    with patch("app.infra.llm_openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()

        # First call: OK response used for conversation creation.
        ok_response = _make_fake_openai_response("Hello Mika! How can I assist you today?")

        # Second call: simulate the BadRequestError we see in production logs.
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
    should surface a mapped HTTP error (e.g. 502 "Upstream OpenAI API error.")
    rather than an unhandled 500 Internal Server Error.
    """
    client = client_with_bad_request_error_on_append

    # First call creates the conversation successfully.
    r1 = client.post(
        "/conversations",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "Hi my name is Mika"}],
        },
    )
    assert r1.status_code == 200
    cid = r1.json()["conversation_id"]

    # Second call triggers BadRequestError inside the adapter.
    r2 = client.post(
        f"/conversations/{cid}",
        json={
            "prompt_slug": "default",
            "messages": [{"role": "user", "content": "What is my name?"}],
        },
    )

    # Desired behaviour (will currently FAIL): a mapped upstream error, not 500.
    assert r2.status_code == 502
    body = r2.json()
    assert body["detail"] == "Upstream OpenAI API error."
    assert "request_id" in body
