.PHONY: up down build test test-backend test-frontend test-watch check-layers lint format backup usage help

IMAGE := conversation-engine

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start both services with hot-reload (detached)
	docker compose up -d
	echo "The frontend is at http://localhost:3000, the API at http://localhost:8000."

down: ## Stop all services
	docker compose down

build: ## Build backend and frontend images (used by docker compose up)
	docker compose build

logs: ## Follow logs for both services
	docker compose logs -f

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests (builds image first)
	docker build -t $(IMAGE) .
	docker run --rm $(IMAGE) python -m pytest -v

test-frontend: ## Run frontend tests
	docker compose run --rm frontend pnpm test

test-watch: ## Run frontend tests in watch mode
	docker compose run --rm frontend pnpm test:watch

smoke: ## Live smoke test of the course-session lifecycle (needs `make up` + real OPENAI_API_KEY; makes real LLM calls)
	python3 scripts/smoke_lesson_lifecycle.py

usage: ## Show token usage per run (last 20), ordered by most recent
	@sqlite3 -column -header data/chat.db \
		"SELECT created_at, prompt_slug, model, input_tokens, output_tokens, (input_tokens + output_tokens) AS total_tokens FROM runs ORDER BY created_at DESC LIMIT 20"

backup: ## Backup the SQLite database to data/backups/ with a timestamp
	mkdir -p data/backups
	@ts=$$(date +%Y%m%d-%H%M%S); sqlite3 data/chat.db .dump > data/backups/chat-$$ts.sql && echo "Backup saved to data/backups/chat-$$ts.sql"

check-layers: ## Enforce architecture layer rules (no upward imports)
	docker build -t $(IMAGE) . -q
	docker run --rm $(IMAGE) python -m pytest tests/test_architecture.py -v

lint: ## Run ruff linter on backend
	docker run --rm $(IMAGE) python -m ruff check .

format: ## Run ruff formatter on backend
	docker run --rm $(IMAGE) python -m ruff format .
