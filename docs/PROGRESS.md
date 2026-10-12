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
- [x] Фаза 1. База данных и вход
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
- Фаза 1. Миграция 1 создаёт 22 таблицы, индексы, триггеры и представления из schema.sql (SQL триггеров и представлений вписан в миграцию дословно, кроме префикса схемы). Миграция 2 — изменения из SPEC 5.2.
- Фаза 1. В миграцию 2 добавлено поле `users.marketing_opt_out` (по умолчанию `false`): SPEC 8.1 говорит, что в `PATCH /me` меняется «согласие на рассылки», а в schema.sql для него нет поля.
- Фаза 1. Группа студента выбирается при регистрации, а не в онбординге: в schema.sql есть CHECK `role <> 'student' OR group_id IS NOT NULL`, поэтому студента без группы создать нельзя. В онбординге группу можно поменять.
- Фаза 1. Код подтверждения почты хранится в Redis (хэш, 30 минут, 5 попыток). Добавлен `POST /auth/resend-code`, иначе с просроченным кодом подтвердить почту нельзя.
- Фаза 1. Лимит входа «5 попыток в минуту с IP» считает только неудачные попытки: в университете много людей выходят в интернет с одного IP.
- Фаза 1. Без подтверждённой почты можно войти и смотреть меню, но нельзя заказывать (проверка появится в фазе 3).
- Фаза 1. Онбординг показывается один раз на устройстве (флаг в localStorage), его можно пропустить.
- Фаза 1. Тесты backend работают с отдельной базой `<имя>_test` (создаётся сама) и Redis db 15, перед каждым тестом таблицы очищаются. Так `make test` не трогает демо-данные.
- Фаза 1. В dev контейнер backend при старте сам применяет миграции и, если база пустая, загружает демо-данные (`AUTO_SEED=true`). Поэтому после `git pull` достаточно `docker compose up -d --build`.
- Фаза 1. Фронт в Docker сам переустанавливает npm-пакеты, если после `git pull` изменился `package-lock.json` (иначе том `node_modules` остаётся старым).
- Фаза 1. Админ имеет доступ к экранам заведующей (SPEC 6: меню, блюда, отчёты — «manager ✔ admin ✔»).

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

## Фаза 1. База данных и вход — 2026-10-12
Сделано:
- SQLAlchemy-модели всех 22 таблиц schema.sql и 4 таблиц из SPEC 5.2 (`app/models/`), ENUM-типы с именами из schema.sql;
- Alembic: `0001_initial_schema` (таблицы, CHECK, UNIQUE, индексы, триггеры `set_order_timestamps` и `log_order_status`, представления `v_dish_allergens`, `v_menu_today`, `v_kitchen_board`), `0002_spec_5_2_changes`; `alembic check` не видит расхождений с моделями;
- `scripts/seed.py`: 2 корпуса, столовая `main`, 3 группы с расписанием на будни, 6 демо-аккаунтов и 20 студентов (пароль `demo1234`), 11 блюд с рецептами и аллергенами, меню на сегодня и завтра; у `student@demo.kz` аллергия на орехи (тяжёлая) и молоко (слабая);
- `scripts/bootstrap.py`: миграции при старте контейнера и автозагрузка демо-данных в пустую базу;
- API: `/auth/register`, `/auth/verify-email`, `/auth/resend-code`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET/PATCH /me`, `GET/PUT /me/allergens`, `DELETE /me/health-consent`, `/canteens`, `/canteens/by-slug/{slug}`, `/groups`, `/allergens`, `/dish-categories`;
- JWT access 15 минут, refresh 30 дней (хэш в `refresh_tokens`, при обновлении старый отзывается), bcrypt, `require_roles(...)`, ошибки в формате SPEC 8 (`DomainError`), лимит неудачных входов в Redis;
- письмо с кодом через SMTP (в dev — Mailpit, http://localhost:8025);
- фронт: вход, регистрация, ввод кода, онбординг (группа, язык, аллергии с согласием), профиль (имя, группа, язык, рассылки, аллергии, баллы, выход), хранение токенов (Zustand + localStorage) с автообновлением, guard-ы по ролям и стартовая страница для каждой роли, навигация по роли, тексты на ru/kk/en.
Тесты: backend 38 (миграции up/down, регистрация, код, вход, лимит, refresh, logout, профиль, аллергии, `require_roles` для 6 ролей, вход 6 демо-аккаунтов после seed), frontend 13 (guard-ы и стартовые страницы всех ролей, формат, ключи i18n).
Отложено / не сделано:
- привязка Telegram и Web Push в профиле — фаза 8.
Известные проблемы:
- нет.
Как проверить:
- `git pull`, затем `docker compose up -d --build` (миграции и демо-данные применятся сами);
- http://localhost:5173 → «Войти» под `student@demo.kz` / `demo1234` → онбординг → меню; под `cook@demo.kz` → кухня, `cashier@demo.kz` → выдача, `manager@demo.kz` → панель, `admin@demo.kz` → админка;
- регистрация с почтой `@uni.kz`: письмо с кодом видно в Mailpit http://localhost:8025;
- пересоздать демо-данные: `docker compose exec backend python -m scripts.seed`.
