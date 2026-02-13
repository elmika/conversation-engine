# Low-Latency Conversational Microservice

FastAPI backend integrating the OpenAI Responses API, with streaming, SQLite persistence, and prompt governance via `prompt_slug`. Light hexagonal layout: `api/`, `domain/`, `application/`, `infra/`.

## Setup (OpenAI API key)

To call the real `/chat` endpoint, the app needs an OpenAI API key. Tests use a mocked LLM and do **not** require a key.

1. Copy the example env file and add your key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```
   Create or manage keys at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

2. When running with Docker, the container must receive this variable. Use either:
   - **`--env-file .env`** (recommended): passes all variables from `.env` into the container.
   - **`-e OPENAI_API_KEY=sk-...`**: pass the key explicitly.

## Example request (`POST /chat`)

Once the container is running on port 8000, you can send a chat request like:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Hello" }
    ]
  }'
```

The response looks like:

```json
{
  "conversation_id": "abc123",
  "assistant_message": "...",
  "model": "gpt-4.1-mini",
  "timings": {
    "ttfb_ms": 0,
    "total_ms": 412
  }
}
```

To continue a conversation, reuse the `conversation_id` from the first response:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "abc123",
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Thanks, can you clarify that last point?" }
    ]
  }'
```

## Example streaming request (`POST /chat/stream`)

To stream tokens from the model as they are generated:

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Stream a short answer." }
    ]
  }'
```

You will see Server-Sent Events like:

```text
event: meta
data: {"conversation_id":"...","model":"gpt-4.1-mini","prompt_slug":"default"}

event: chunk
data: {"delta":"First part ..."}

event: chunk
data: {"delta":"Next part ..."}

event: done
data: {"conversation_id":"...","assistant_message":"Full answer ...","model":"gpt-4.1-mini","timings":{"ttfb_ms":10,"total_ms":120}}
```

## Run and test with Docker (no local install)

From the repo root:

**Build the image**

```bash
docker build -t open-ai .
```

**Run the app** (with API key so `/chat` works)

```bash
docker run --rm -p 8000:8000 --env-file .env open-ai
```

If you prefer not to use a file: `docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-your-key open-ai`.

- Health: http://127.0.0.1:8000/healthz  
- API docs: http://127.0.0.1:8000/docs  

**Run tests** (no API key needed)

```bash
docker run --rm open-ai pytest -v
```

Test gate: fix any failing tests before considering a change complete.

---

## Run locally (optional)

If you have Python and pip:

```bash
cp .env.example .env   # then set OPENAI_API_KEY in .env
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Tests: `pytest` or `pytest -v`.

---

## Risks and future improvements

For a deeper discussion of streaming and persistence risks, see:

- [`RISKS-AND-IMPROVEMENTS.md`](RISKS-AND-IMPROVEMENTS.md)
