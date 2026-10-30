# Multi-stage: builder (deps + app + tests), prod (slim, app only), runner (default: app + tests, non-root).
# Build default (run app or tests):  docker build -t conversation-engine .
# Build slimmer prod image:          docker build --target prod -t conversation-engine:prod .
#
# Dependencies come from uv.lock (exact versions + hashes) via `uv sync --locked`, which fails
# the build if uv.lock is out of date with pyproject.toml. --no-build: prebuilt wheels only, so
# no package's setup code runs at install time (the project itself isn't installed, see
# [tool.uv] in pyproject.toml). They go into /opt/venv, which is on PATH, so
# `python -m pytest` / `uvicorn` work exactly as before.

# ---- Base: Python + uv, shared by builder and prod ----
FROM python:3.11-slim AS base

# Keep in sync with the uv version in .github/workflows/ci.yml.
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY pyproject.toml uv.lock ./

# ---- Builder: runtime + dev dependencies, app + tests ----
FROM base AS builder

RUN uv sync --locked --no-build --no-cache

COPY app/ app/
COPY tests/ tests/
COPY prompts/ prompts/

# ---- Prod (optional): runtime deps only, smaller image ----
FROM base AS prod

RUN uv sync --locked --no-build --no-cache --no-dev \
    && rm /usr/local/bin/uv

COPY app/ app/
COPY prompts/ prompts/

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
