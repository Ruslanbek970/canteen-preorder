# Прогресс

Обновляется после каждой фазы. Формат записи:

```
## Фаза N. Название — дата
Сделано:
-
Отложено / не сделано:
-
Известные проблемы:
-
Как проверить:
-
```

## Статус фаз

- [x] Фаза 0. Каркас
- [ ] Фаза 1. База данных и вход
- [ ] Фаза 2. Каталог и меню
- [ ] Фаза 3. Слоты и заказ
- [ ] Фаза 4. Оплата и QR
- [ ] Фаза 5. Кухня
- [ ] Фаза 6. Выдача и касса
- [ ] Фаза 7. Панель заведующей
- [ ] Фаза 8. Скидки и уведомления
- [ ] Фаза 9. Прогноз спроса
- [ ] Фаза 10. Админка
- [ ] Фаза 11. Качество и нагрузка
- [ ] Фаза 12. Продакшен
- [ ] Фаза 13. Документация и защита

## Решения

Сюда записываются решения, принятые по ходу работы, если в ТЗ чего-то не хватало.

- Фаза 0. `/health/ready` (SPEC 8.10) добавлен сразу вместе с `/health`: он нужен для healthcheck и CD, а проверка БД и Redis — это одна функция.
- Фаза 0. React 18 + React Router 6 (флаги v7 включены), Tailwind 3.4 с `darkMode: 'media'` (тёмная тема по системной настройке, SPEC 9). Node 22 в Docker и CI.
- Фаза 0. Пакеты backend ставятся через `pip install -e ".[dev]"` из `backend/pyproject.toml`, без отдельного менеджера зависимостей.
- Фаза 0. Dev-фронт в Docker проксирует `/api` и `/ws` на `backend:8000` через Vite (`VITE_API_PROXY_TARGET`), поэтому в браузере всё идёт с `localhost:5173`.
- Фаза 0. Защита страниц по ролям (guard-ы) появится в фазе 1 вместе со входом; сейчас страницы по ролям открыты и пустые, на главной есть ссылки на все разделы.
- Фаза 0. `make e2e` и `make load-test` пока печатают сообщение: Playwright и k6 появятся в фазе 11.

## Журнал

## Фаза 0. Каркас — 2026-10-12
Сделано:
- структура репозитория по SPEC 4 (пустые пакеты backend, папки фич frontend, `infra/`, `docs/adr/`);
- backend: `pyproject.toml` (FastAPI, SQLAlchemy, psycopg, Alembic, Redis; dev: pytest, ruff), `app/config.py` (pydantic-settings, все переменные из SPEC 14.5), `app/db.py`, `app/redis_client.py`, `app/utils/time.py` (`today_local()` в Asia/Almaty), `GET /api/v1/health` и `GET /api/v1/health/ready`, Swagger на `/api/docs`, многоэтапный Dockerfile с непривилегированным пользователем и healthcheck;
- frontend: Vite + React + TypeScript strict, React Router, TanStack Query, Tailwind, i18next (ru/kk/en, переключатель языка), пустые страницы по ролям (`/menu`, `/orders`, `/profile`, `/kitchen`, `/pickup`, `/pos`, `/manager`, `/admin`, `/login`, `/c/:slug`), `formatPrice` и `formatTime`, ESLint + Prettier, Vitest, Dockerfile (dev-сервер и prod-сборка в nginx);
- `docker-compose.yml`: db (postgres 16), redis, backend (uvicorn --reload), frontend (vite dev), mailpit;
- `Makefile`, `.env.example`, `.pre-commit-config.yaml`, `README.md`;
- CI `.github/workflows/ci.yml`: ruff check/format, pytest с покрытием на postgres и redis, eslint, prettier, tsc, vitest, vite build, сборка Docker-образов.
Тесты: backend 5 (health, ready, часовой пояс), frontend 10 (роутинг, формат цены и времени, одинаковые ключи i18n).
Отложено / не сделано:
- первый прогон CI на GitHub: репозиторий ещё не создан;
- alembic.ini и миграции, guard-ы ролей — фаза 1; worker, bot, prometheus, grafana, nginx для prod — по своим фазам.
Известные проблемы:
- в Linux при монтировании `./backend` в контейнер файлы принадлежат хосту; кэши ruff, pytest и coverage поэтому вынесены в `/tmp` контейнера (переменные в `docker-compose.yml`).
Как проверить:
- `make dev`, затем открыть http://localhost:5173 (главная со ссылками на разделы, переключатель RU/KK/EN) и http://localhost:8000/api/v1/health (`{"status":"ok"}`); `/api/v1/health/ready` показывает, что БД и Redis доступны;
- `make lint` и `make test` проходят;
- после пуша на GitHub вкладка Actions: workflow CI зелёный.
