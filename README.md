# Canteen Pre-order

Веб-приложение предзаказа в университетской столовой: студент заказывает обед до перемены, выбирает слот выдачи и забирает заказ по QR. Дипломный проект.

- ТЗ: [`docs/SPEC.md`](docs/SPEC.md)
- Схема БД: [`docs/schema.sql`](docs/schema.sql), ER-диаграмма: [`docs/er_diagram.png`](docs/er_diagram.png)
- Прогресс по фазам: [`docs/PROGRESS.md`](docs/PROGRESS.md)
- Правила для Claude Code: [`CLAUDE.md`](CLAUDE.md)

## Стек

Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Redis.
Frontend: React + TypeScript + Vite, React Router, TanStack Query, Tailwind, i18next (ru, kk, en).
Инфраструктура: Docker Compose, GitHub Actions.

## Запуск

Нужны Docker Desktop (с Docker Compose) и `make`.

```bash
git clone <repo-url> canteen-preorder && cd canteen-preorder
make dev
```

`make dev` создаёт `.env` из `.env.example` (если его нет) и поднимает сервисы:

| Что | Адрес |
|---|---|
| Фронтенд | http://localhost:5173 |
| API, проверка живости | http://localhost:8000/api/v1/health |
| Swagger | http://localhost:8000/api/docs |
| Mailpit (письма) | http://localhost:8025 |

Остановить: `make down`. Логи: `make logs`.

## Команды

```bash
make dev        # поднять всё локально
make down       # остановить
make test       # тесты backend и frontend
make lint       # ruff, eslint, tsc, prettier
make format     # автоформатирование
make migrate    # миграции (с фазы 1)
make seed       # демо-данные (с фазы 1)
```

## Разработка без Docker

```bash
# backend
cd backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest

# frontend
cd frontend
npm ci
npm run lint && npm run typecheck && npm test
npm run dev     # http://localhost:5173, /api проксируется на localhost:8000
```

Pre-commit хуки (ruff, eslint, prettier): `pip install pre-commit && pre-commit install`.
