COMPOSE ?= docker compose
BACKEND = $(COMPOSE) exec backend

.PHONY: dev down logs ps migrate seed test test-backend test-frontend lint format e2e load-test \
	monitoring backup restore

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

load-test: ## k6 order rush: 500 students, 6 slots x 30 places (docs/load-test.md)
	$(BACKEND) python -m scripts.load_setup
	$(COMPOSE) --profile load run --rm k6
	$(BACKEND) python -m scripts.load_check

monitoring: ## Prometheus http://localhost:9090 and Grafana http://localhost:3000 (admin/admin)
	$(COMPOSE) --profile monitoring up -d prometheus grafana

# Production server (docs/deployment.md)
PROD = docker compose -f docker-compose.prod.yml

backup: ## a database dump now, into the `backups` volume
	$(PROD) exec backup sh /scripts/backup.sh once

restore: ## make restore FILE=/backups/canteen-....dump [DB=canteen] (default: test database)
	$(PROD) exec backup sh /scripts/restore.sh $(FILE) $(DB)
