# Low-Latency Conversational Microservice

FastAPI backend integrating the OpenAI Responses API, with streaming, SQLite persistence, and prompt governance via `prompt_slug`. Light hexagonal layout: `api/`, `domain/`, `application/`, `infra/`.

## Run and test with Docker (no local install)

From the repo root:

**Build the image**

```bash
docker build -t open-ai .
```

**Run the app**

```bash
docker run --rm -p 8000:8000 open-ai
```

- Health: http://127.0.0.1:8000/healthz  
- API docs: http://127.0.0.1:8000/docs  

Optional: pass env with `-e OPENAI_API_KEY=...` or `--env-file .env` (once chat endpoints exist).

**Run tests**

```bash
docker run --rm open-ai pytest -v
```

Test gate: fix any failing tests before considering a change complete.

---

## Run locally (optional)

If you have Python and pip:

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Tests: `pytest` or `pytest -v`. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` when using chat.
