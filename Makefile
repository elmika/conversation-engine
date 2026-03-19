.PHONY: up down build test test-backend test-frontend test-watch lint format help

IMAGE := conversation-engine

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start both services with hot-reload
	docker compose up

down: ## Stop all services
	docker compose down

build: ## Build backend and frontend production images
	docker build -t $(IMAGE) .
	docker build -t $(IMAGE)-frontend ./frontend

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests (builds image first)
	docker build -t $(IMAGE) .
	docker run --rm $(IMAGE) python -m pytest -v

test-frontend: ## Run frontend tests
	docker compose run --rm frontend pnpm test

test-watch: ## Run frontend tests in watch mode
	docker compose run --rm frontend pnpm test:watch

lint: ## Run ruff linter on backend
	docker run --rm $(IMAGE) python -m ruff check .

format: ## Run ruff formatter on backend
	docker run --rm $(IMAGE) python -m ruff format .
