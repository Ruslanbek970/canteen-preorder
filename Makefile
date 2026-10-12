COMPOSE ?= docker compose
BACKEND = $(COMPOSE) exec backend

.PHONY: dev down logs ps migrate seed test test-backend test-frontend lint format e2e load-test

dev: ## start the dev environment (frontend: http://localhost:5173)
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build
	@echo "Frontend: http://localhost:5173  API: http://localhost:8000/api/v1/health  Mailpit: http://localhost:8025"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

migrate:
	$(BACKEND) alembic upgrade head

seed:
	$(BACKEND) python -m scripts.seed

test: test-backend test-frontend

test-backend:
	$(COMPOSE) run --rm --no-deps backend pytest --cov=app

test-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm test

lint:
	$(COMPOSE) run --rm --no-deps backend sh -c "ruff check . && ruff format --check ."
	$(COMPOSE) run --rm --no-deps frontend sh -c "npm run lint && npm run typecheck && npm run format:check"

format:
	$(COMPOSE) run --rm --no-deps backend sh -c "ruff format . && ruff check --fix ."
	$(COMPOSE) run --rm --no-deps frontend npm run format

e2e: ## Playwright end-to-end test (needs `make dev` running)
	cd frontend && npm run e2e

load-test:
	@echo "k6 load test is added in phase 11 (SPEC 13)."
