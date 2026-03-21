.PHONY: up down build test test-backend test-frontend test-watch lint format backup help

IMAGE := conversation-engine

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start both services with hot-reload (detached)
	docker compose up -d
	echo "The frontend is at http://localhost:3000, the API at http://localhost:8000."

down: ## Stop all services
	docker compose down

build: ## Build backend and frontend production images (tagged :prod)
	docker build -t $(IMAGE):prod .
	docker build -t $(IMAGE)-frontend:prod ./frontend

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

backup: ## Backup the SQLite database to data/backups/ with a timestamp
	mkdir -p data/backups
	@ts=$$(date +%Y%m%d-%H%M%S); sqlite3 data/chat.db .dump > data/backups/chat-$$ts.sql && echo "Backup saved to data/backups/chat-$$ts.sql"

lint: ## Run ruff linter on backend
	docker run --rm $(IMAGE) python -m ruff check .

format: ## Run ruff formatter on backend
	docker run --rm $(IMAGE) python -m ruff format .
