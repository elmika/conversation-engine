# Multi-stage: builder (deps + app + tests), prod (slim, app only), runner (default: app + tests, non-root).
# Build default (run app or tests):  docker build -t open-ai .
# Build slimmer prod image:          docker build --target prod -t open-ai:prod .

# ---- Builder ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY app/ app/
COPY tests/ tests/

# ---- Prod (optional): runtime deps only, smaller image ----
FROM python:3.11-slim AS prod

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .
COPY --from=builder /app/app ./app

RUN mkdir -p /app/data \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- Runner (default): same image runs app or pytest, non-root ----
FROM builder AS runner

RUN mkdir -p /app/data \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
