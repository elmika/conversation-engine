.PHONY: hooks merge up down build test test-backend test-frontend test-watch check-layers lint format backup usage help deploy deploy-backend deploy-frontend fly-stop fly-start

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

smoke-openai: ## Live smoke test of the OpenAI Responses API shape (needs local OPENAI_API_KEY + `pip install openai`; bypasses Docker/the app; makes a real LLM call)
	python3 scripts/smoke_openai_direct.py

check-keys: ## Verify OPENAI/ANTHROPIC API keys in .env are accepted and in sync with the api container (free, no tokens)
	python3 scripts/check_api_keys.py

check-models: ## List provider models not yet in model_registry.py / pricing.py, and registered ones no longer served (free, no tokens)
	python3 scripts/check_new_models.py

usage: ## Show token usage per run (last 20), ordered by most recent
	@sqlite3 -column -header data/chat.db \
		"SELECT created_at, prompt_slug, model, input_tokens, output_tokens, (input_tokens + output_tokens) AS total_tokens FROM runs ORDER BY created_at DESC LIMIT 20"

backup: ## Backup the SQLite database to data/backups/ with a timestamp
	mkdir -p data/backups
	@ts=$$(date +%Y%m%d-%H%M%S); sqlite3 data/chat.db .dump > data/backups/chat-$$ts.sql && echo "Backup saved to data/backups/chat-$$ts.sql"

check-layers: ## Enforce architecture layer rules (no upward imports)
	docker build -t $(IMAGE) . -q
	docker run --rm $(IMAGE) python -m pytest tests/test_architecture.py -v

lint: ## Run ruff linter on the working tree (mounts the repo into the image)
	docker run --rm -v "$(PWD)":/src -w /src $(IMAGE) python -m ruff check .

format: ## Run ruff formatter on the working tree (mounts the repo into the image)
	docker run --rm -v "$(PWD)":/src -w /src $(IMAGE) python -m ruff format .

hooks: ## Install the repo's git hooks (pre-push blocks direct pushes to main)
	git config core.hooksPath scripts/git-hooks

merge: ## Merge BRANCH into main via a GitHub PR once its CI passes (merge commit, like --no-ff)
	@test -n "$(BRANCH)" || { echo "usage: make merge BRANCH=<branch>"; exit 1; }
	git fetch origin
	@git merge-base --is-ancestor origin/main $(BRANCH) || { \
		echo "$(BRANCH) is behind main. Update it first: git checkout $(BRANCH) && git merge origin/main"; \
		exit 1; }
	git push -u origin $(BRANCH)
	@gh pr view $(BRANCH) --json state -q .state 2>/dev/null | grep -q OPEN || \
		gh pr create --base main --head $(BRANCH) --fill
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12; do \
		gh pr checks $(BRANCH) >/dev/null 2>&1; [ $$? -ne 1 ] && break; sleep 5; done
	gh pr checks $(BRANCH) --watch --fail-fast
	gh pr merge $(BRANCH) --merge
	git checkout main && git pull --ff-only

deploy-backend: ## Deploy the API to Fly.io (app: learning-platform, config: fly.toml)
	fly deploy -c fly.toml

deploy-frontend: ## Deploy the frontend to Fly.io (app: skillforge-web, config: frontend/fly.toml)
	cd frontend && fly deploy

deploy: deploy-backend deploy-frontend ## Deploy both API and frontend to Fly.io

fly-stop: ## Scale both Fly apps to 0 machines (stops compute billing; app/volume/DNS stay intact)
	fly scale count 0 -a learning-platform --yes
	fly scale count 0 -a skillforge-web --yes

fly-start: ## Scale both Fly apps back to 1 machine
	fly scale count 1 -a learning-platform --yes
	fly scale count 1 -a skillforge-web --yes
