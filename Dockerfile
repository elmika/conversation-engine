# Day 1 minimal image: run app or tests. Harden in Day 8 (multi-stage, non-root).
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY app/ app/
COPY tests/ tests/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
