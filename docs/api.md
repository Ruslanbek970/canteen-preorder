# API

Полное описание со схемами запросов и ответов — Swagger:
- локально: http://localhost:8000/api/docs (OpenAPI JSON: `/api/openapi.json`);
- на сервере: `https://<домен>/api/docs`.

Все пути начинаются с `/api/v1`. Авторизация: заголовок `Authorization: Bearer <access_token>`.
Access-токен живёт 15 минут, refresh-токен 30 дней. Каждый ответ несёт заголовок
`X-Request-ID`: по нему запрос можно найти в логах.

## Формат ошибки (SPEC 8)

```json
{ "error": { "code": "slot_full", "message": "В этом слоте нет мест", "details": {} } }
```

| HTTP | Когда |
|---|---|
| 401 | нет токена или он истёк |
| 403 | у роли нет доступа, почта не подтверждена (`email_not_verified`) |
| 404 | нет такого объекта или он чужой (чужой заказ тоже 404) |
| 409 | бизнес-конфликт: `slot_full`, `sold_out`, `invalid_transition`, `cancel_too_late` и др. |
| 422 | неверные данные (`validation_error`, `allergy_blocked`, `allergy_ack_required`, `menu_date_unavailable` и др.) |
| 429 | лимит частоты (`rate_limited`): 5 неудачных входов в минуту с IP, 10 заказов в минуту |

## Главные сценарии

### Вход

```bash
curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "student@demo.kz", "password": "demo1234"}'
# {"access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900}
```

Регистрация: `POST /auth/register` → код на почту (в dev смотреть в Mailpit, http://localhost:8025)
→ `POST /auth/verify-email`. Продление: `POST /auth/refresh`.

### Заказ студента

1. `GET /canteens` — столовые.
2. `GET /canteens/{id}/menu?date=YYYY-MM-DD` — меню дня; у каждого блюда для вошедшего
   пользователя есть `unsafe_for_me` (аллерген `severe`) и `warning_for_me` (`mild`/`moderate`).
3. `GET /canteens/{id}/slots?date=` — слоты, подходящие по расписанию группы (`hidden`
   объясняет, сколько скрыто и почему).
4. `POST /orders`:
   ```json
   { "canteen_id": 1, "pickup_slot_id": 42,
     "items": [{ "menu_item_id": 7, "quantity": 2 }],
     "allergy_warning_ack": false }
   ```
   Ответ `201` содержит заказ (`pending_payment`, номер `A-017`) и `payment.payment_url` на
   mock-оплату. `409 slot_full` / `sold_out` — места или порции закончились,
   `422 allergy_blocked` — блюдо с аллергеном `severe`, `422 allergy_ack_required` — нужно
   подтвердить `mild`.
5. `POST /payments/mock/{payment_id}/confirm` (или `/fail`) — mock-оплата; заказ становится
   `paid`, у него появляется QR (`qr_token`).
6. `GET /orders/{id}` и WebSocket `/ws/me?token=<access_token>` — статус в реальном времени
   (`order.paid`, `order.status_changed` со статусом и номером полки, `order.cancelled`).
7. `POST /orders/{id}/cancel` — отмена (неоплаченный — всегда, оплаченный — не позже чем за
   30 минут до слота, с возвратом). `POST /orders/{id}/repeat` — собрать корзину из прошлого
   заказа.

### Кухня (cook)

- `GET /kitchen/board` — заказы дня по слотам; WebSocket `/ws/kitchen/{canteen_id}` обновляет
  доску сам.
- `POST /kitchen/slots/{slot_id}/start` — взять слот в работу (`paid → cooking` для всех
  заказов слота).
- `POST /kitchen/orders/{id}/status` с `{"status": "ready"}` — готов, полка назначается сама.
- `GET /kitchen/orders/{id}/label` — наклейка; `POST /kitchen/waste`, `POST /kitchen/close-day` —
  списания.

### Выдача и касса (cashier)

- `GET /pickup/scan/{qr_token}` или `GET /pickup/by-number/{номер}` (`A7`, `a-007` и `7` найдут `A-007`) →
  `POST /pickup/orders/{id}/confirm`.
- `POST /pos/sales` — продажа на кассе без предзаказа.

### Заведующая (canteen_manager)

- `PUT /manager/menu` — меню дня; `GET/PATCH /manager/slots` — слоты, ёмкость, закрытие.
- `GET /manager/dashboard` — сегодня: заказы, выручка, остатки, подсказки.
- `GET /manager/reports/{sales|waste|peak-hours|ratings|forecast}?from=&to=` и `.csv`.
- `GET /manager/promotions`, `POST /manager/promotions/{id}/approve` или `/reject` — предложенные
  скидки на остатки; `POST /manager/promotions` — скидка на тихий слот.

### Администратор (admin)

- `/admin/users`, `/admin/canteens`, `/admin/buildings`, `/admin/groups`.
- `POST /admin/schedule/import?dry_run=true` — проверка CSV расписания, без `dry_run` — импорт.

Сотрудник видит только свою столовую: запрос к чужой даёт 404 или пустой ответ.

## Все эндпоинты

### health

| Метод | Путь | |
|---|---|---|
| GET | `/health` | Liveness: the process is up. |
| GET | `/health/ready` | Readiness: database and Redis are reachable. |

### auth

| Метод | Путь | |
|---|---|---|
| POST | `/auth/register` | Register |
| POST | `/auth/verify-email` | Verify Email |
| POST | `/auth/resend-code` | Resend Code |
| POST | `/auth/login` | Login |
| POST | `/auth/refresh` | Refresh |
| POST | `/auth/logout` | Logout |

### profile

| Метод | Путь | |
|---|---|---|
| GET | `/me` | Get Me |
| PATCH | `/me` | Patch Me |
| GET | `/me/allergens` | Get Allergens |
| PUT | `/me/allergens` | Put Allergens |
| DELETE | `/me/health-consent` | Delete Consent |
| POST | `/me/telegram/link-code` | Telegram Link Code |
| DELETE | `/me/telegram` | Telegram Unlink |
| POST | `/me/push-subscriptions` | Push Subscribe |
| DELETE | `/me/push-subscriptions` | Push Unsubscribe |

### reference

| Метод | Путь | |
|---|---|---|
| GET | `/canteens` | List Canteens |
| GET | `/canteens/by-slug/{slug}` | Canteen By Slug |
| GET | `/groups` | List Groups |
| GET | `/allergens` | List Allergens |
| GET | `/dish-categories` | List Categories |

### menu

| Метод | Путь | |
|---|---|---|
| GET | `/canteens/{canteen_id}/menu` | Menu of the day. For a signed-in user each dish has `unsafe_for_me` / `warning_for_me`. |
| GET | `/dishes/{dish_id}` | Dish Card |

### manager: catalog

| Метод | Путь | |
|---|---|---|
| GET | `/manager/dishes` | List Dishes |
| POST | `/manager/dishes` | Create Dish |
| GET | `/manager/dishes/{dish_id}` | Get Dish |
| PATCH | `/manager/dishes/{dish_id}` | Update Dish |
| GET | `/manager/ingredients` | List Ingredients |
| POST | `/manager/ingredients` | Create Ingredient |
| GET | `/manager/menu` | Get Menu |
| PUT | `/manager/menu` | Put Menu |
| PATCH | `/manager/menu-items/{item_id}` | Patch Menu Item |

### admin

| Метод | Путь | |
|---|---|---|
| GET | `/admin/users` | List Users |
| POST | `/admin/users` | Create User |
| PATCH | `/admin/users/{user_id}` | Update User |
| GET | `/admin/canteens` | List Canteens |
| POST | `/admin/canteens` | Create Canteen |
| PATCH | `/admin/canteens/{canteen_id}` | Update Canteen |
| GET | `/admin/buildings` | List Buildings |
| POST | `/admin/buildings` | Create Building |
| GET | `/admin/groups` | List Groups |
| POST | `/admin/groups` | Create Group |
| POST | `/admin/schedule/import` | Import Schedule |

### slots

| Метод | Путь | |
|---|---|---|
| GET | `/canteens/{canteen_id}/slots` | Slots that suit the user (SPEC 7.4): no lesson overlap, after the cutoff, not full. |
| GET | `/manager/slots` | Manager Slots |
| POST | `/manager/slots/generate` | The worker does this every day at 05:00; the button is for a missed day. |
| PATCH | `/manager/slots/{slot_id}` | Patch Slot |

### orders

| Метод | Путь | |
|---|---|---|
| POST | `/orders` | One transaction: allergies -> portions -> slot -> number -> order -> payment (SPEC 7.5). |
| GET | `/orders` | My Orders |
| GET | `/orders/{order_id}` | Get Order |
| POST | `/orders/{order_id}/cancel` | Cancel Order |
| POST | `/orders/{order_id}/repeat` | Repeat Order |
| POST | `/orders/{order_id}/pay` | A payment link for an unpaid order (again after «Отказ»). |

### payments

| Метод | Путь | |
|---|---|---|
| GET | `/payments/{payment_id}` | Get Payment |
| POST | `/payments/mock/{payment_id}/confirm` | Mock Confirm |
| POST | `/payments/mock/{payment_id}/fail` | Mock Fail |
| POST | `/payments/webhook/{provider}` | For a real provider later (SPEC 8.5). Signature checks belong to the provider class. |

### kitchen

| Метод | Путь | |
|---|---|---|
| GET | `/kitchen/board` | Today's paid / cooking / ready orders grouped by slot. |
| GET | `/kitchen/prep-summary` | Prep Summary |
| POST | `/kitchen/orders/{order_id}/status` | Set Status |
| POST | `/kitchen/slots/{slot_id}/start` | Start Slot |
| GET | `/kitchen/orders/{order_id}/label` | Label |
| POST | `/kitchen/close-day` | Close Day |
| GET | `/kitchen/waste` | Waste List |
| POST | `/kitchen/waste` | Record Waste |

### pickup

| Метод | Путь | |
|---|---|---|
| GET | `/pickup/scan/{qr_token}` | Scan |
| GET | `/pickup/by-number/{order_number}` | Today's order by its number; `A7`, `a-007` and `7` all find `A-007`. |
| POST | `/pickup/orders/{order_id}/confirm` | Confirm |
| POST | `/pos/sales` | Pos Sale |

### reviews

| Метод | Путь | |
|---|---|---|
| POST | `/order-items/{item_id}/review` | Create Review |

### reports

| Метод | Путь | |
|---|---|---|
| GET | `/manager/dashboard` | Dashboard |
| GET | `/manager/reports/sales` | Sales |
| GET | `/manager/reports/waste` | Waste |
| GET | `/manager/reports/peak-hours` | Peak Hours |
| GET | `/manager/reports/ratings` | Ratings |
| GET | `/manager/reports/forecast` | Forecast |
| GET | `/manager/reports/{name}.csv` | Report Csv |

### promotions

| Метод | Путь | |
|---|---|---|
| GET | `/manager/promotions` | List Promotions |
| POST | `/manager/promotions` | Create Off Peak |
| POST | `/manager/promotions/{promotion_id}/approve` | Approve |
| POST | `/manager/promotions/{promotion_id}/reject` | Reject |

### notifications

| Метод | Путь | |
|---|---|---|
| GET | `/notifications` | My Notifications |
| GET | `/notifications/push-key` | The VAPID public key for the browser; 404 while Web Push is not configured. |
| POST | `/notifications/{notification_id}/read` | Mark Read |
| POST | `/notifications/read-all` | Mark All Read |
