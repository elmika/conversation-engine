# Low-Latency Conversational Microservice

FastAPI backend integrating the OpenAI Responses API, with streaming, SQLite persistence, and prompt governance via `prompt_slug`. Light hexagonal layout: `api/`, `domain/`, `application/`, `infra/`.

## Setup (OpenAI API key)

To call the real conversation endpoints, the app needs an OpenAI API key. Tests use a mocked LLM and do **not** require a key.

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

## Run and test with Docker (no local install)

From the repo root. The image runs as a non-root user and uses a multi-stage build.

**Build the image** (default: includes app + tests)

```bash
docker build -t open-ai .
```

Optional: build a slimmer production-only image (no pytest):

```bash
docker build --target prod -t open-ai:prod .
```

**Run the app** (with API key so conversation endpoints work)

```bash
docker run --rm -p 8000:8000 --env-file .env open-ai
```

If you prefer not to use a file: `docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-your-key open-ai`.

- Health: http://127.0.0.1:8000/healthz  
- API docs: http://127.0.0.1:8000/docs  

**Run tests** (no API key needed; use default image, not `open-ai:prod`)

```bash
docker run --rm open-ai pytest -v
```

Test gate: fix any failing tests before considering a change complete.

## Run locally (optional)

If you have Python and pip:

```bash
cp .env.example .env   # then set OPENAI_API_KEY in .env
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Tests: `pytest` or `pytest -v`.

## More

- **[API.md](API.md)** — Example requests, response shapes, and quick command-line tests for all endpoints.
- **[RISKS-AND-IMPROVEMENTS.md](RISKS-AND-IMPROVEMENTS.md)** — Streaming and persistence risks, and future improvements.
