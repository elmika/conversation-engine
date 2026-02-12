# Low-Latency Conversational Microservice

FastAPI backend integrating the OpenAI Responses API, with streaming, SQLite persistence, and prompt governance via `prompt_slug`. Light hexagonal layout: `api/`, `domain/`, `application/`, `infra/`.

## Run the app

```bash
cd /path/to/open-ai
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

- Health: http://127.0.0.1:8000/healthz  
- API docs: http://127.0.0.1:8000/docs  

Optional: copy `.env.example` to `.env` and set `OPENAI_API_KEY` (required once chat endpoints are used).

## Test

```bash
pytest
```

Verbose:

```bash
pytest -v
```

Test gate: fix any failing tests before considering a change complete.
