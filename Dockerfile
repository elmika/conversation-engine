# Multi-stage: builder (deps + app + tests), prod (slim, app only), runner (default: app + tests, non-root).
# Build default (run app or tests):  docker build -t conversation-engine .
# Build slimmer prod image:          docker build --target prod -t conversation-engine:prod .

# ---- Builder ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install runtime + dev dependencies first for layer caching
COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt pytest pytest-asyncio ruff

# Copy source and install the package itself (no deps re-install)
COPY app/ app/
COPY tests/ tests/
COPY prompts/ prompts/
RUN pip install --no-cache-dir -e . --no-deps

# ---- Prod (optional): runtime deps only, smaller image ----
FROM python:3.11-slim AS prod

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY prompts/ prompts/
RUN pip install --no-cache-dir -e . --no-deps

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
