-- =====================================================================
--  Система предзаказа в университетской столовой
--  Схема базы данных, PostgreSQL 13+ (проверено на 16)
--
--  КАК ЗАПУСТИТЬ В pgAdmin
--    1. Servers -> ваш сервер -> Databases -> правой кнопкой -> Create -> Database...
--       Имя: canteen_db -> Save.
--    2. Выберите canteen_db -> Tools -> Query Tool.
--    3. Откройте этот файл (иконка папки) или вставьте текст целиком.
--    4. Нажмите F5 (Execute script). Должно закончиться без ошибок.
--    5. Обновите дерево (F5 на canteen_db): Schemas -> canteen -> Tables, там 22 таблицы.
--    6. Диаграмма: правой кнопкой по canteen_db -> ERD For Database.
--    В Query Tool перед своими запросами пишите:  SET search_path TO canteen;
--
--  Скрипт можно запускать повторно: он удаляет схему canteen и создаёт её заново.
--  Если нужны пустые таблицы без тестовых данных, удалите раздел 6.
--
--  Содержание
--    1. Типы (ENUM)
--    2. Таблицы (22): кампус и люди, меню и еда, слоты и скидки,
--       заказы и оплата, отзывы и аналитика
--    3. Индексы
--    4. Триггеры (время смены статуса + история статусов)
--    5. Представления (меню на сегодня, экран кухни)
--    6. Тестовые данные
--    7. Примеры запросов
-- =====================================================================

DROP SCHEMA IF EXISTS canteen CASCADE;
CREATE SCHEMA canteen;
SET search_path TO canteen;

-- =====================================================================
-- 1. ТИПЫ
-- =====================================================================
CREATE TYPE user_role            AS ENUM ('student', 'teacher', 'cook', 'cashier', 'canteen_manager', 'admin');
CREATE TYPE order_status         AS ENUM ('pending_payment', 'paid', 'cooking', 'ready', 'picked_up', 'cancelled', 'no_show');
CREATE TYPE order_channel        AS ENUM ('mobile_app', 'web_qr', 'cashier');
CREATE TYPE payment_method       AS ENUM ('kaspi_qr', 'bank_card', 'cash');
CREATE TYPE payment_status       AS ENUM ('pending', 'succeeded', 'failed', 'refunded');
CREATE TYPE promotion_type       AS ENUM ('leftover', 'off_peak', 'loyalty');
CREATE TYPE promotion_status     AS ENUM ('proposed', 'active', 'rejected', 'expired');
CREATE TYPE notification_channel AS ENUM ('push', 'telegram', 'sms');
CREATE TYPE allergy_severity     AS ENUM ('mild', 'moderate', 'severe');
CREATE TYPE waste_reason         AS ENUM ('expired', 'uncollected_order', 'damaged', 'other');

-- =====================================================================
-- 2. ТАБЛИЦЫ
-- =====================================================================

-- ---------- 2.1 Кампус и люди ----------------------------------------

CREATE TABLE buildings (
    id       INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name     VARCHAR(100) NOT NULL UNIQUE,
    address  VARCHAR(255)
);
COMMENT ON TABLE buildings IS 'Корпуса университета. В них находятся столовые и проходят пары.';

CREATE TABLE canteens (
    id                     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    building_id            INT NOT NULL REFERENCES buildings(id),
    name                   VARCHAR(100) NOT NULL,
    opens_at               TIME NOT NULL,
    closes_at              TIME NOT NULL,
    default_slot_minutes   SMALLINT NOT NULL DEFAULT 10 CHECK (default_slot_minutes BETWEEN 5 AND 60),
    default_slot_capacity  SMALLINT NOT NULL DEFAULT 30 CHECK (default_slot_capacity > 0),
    is_active              BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (opens_at < closes_at)
);
COMMENT ON TABLE canteens IS 'Столовые кампуса. Длина слота и вместимость = сколько заказов кухня успевает собрать за один слот.';

CREATE TABLE student_groups (
    id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        VARCHAR(20) NOT NULL UNIQUE,          -- например, SE-2301
    faculty     VARCHAR(100),
    study_year  SMALLINT CHECK (study_year BETWEEN 1 AND 6)
);
COMMENT ON TABLE student_groups IS 'Учебные группы. Студент состоит в одной группе, у группы есть расписание пар.';

CREATE TABLE users (
    id                      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name               VARCHAR(150) NOT NULL,
    email                   VARCHAR(150) NOT NULL UNIQUE,
    phone                   VARCHAR(20) UNIQUE,
    password_hash           VARCHAR(255) NOT NULL,
    role                    user_role NOT NULL DEFAULT 'student',
    group_id                INT REFERENCES student_groups(id),   -- только у студентов
    canteen_id              INT REFERENCES canteens(id),         -- только у сотрудников столовой
    preferred_language      CHAR(2) NOT NULL DEFAULT 'ru' CHECK (preferred_language IN ('kk', 'ru', 'en')),
    telegram_chat_id        BIGINT UNIQUE,
    health_data_consent_at  TIMESTAMPTZ,                         -- аллергии храним только после согласия
    loyalty_points          INT NOT NULL DEFAULT 0 CHECK (loyalty_points >= 0),
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (role <> 'student' OR group_id IS NOT NULL),
    CHECK (role NOT IN ('cook', 'cashier', 'canteen_manager') OR canteen_id IS NOT NULL)
);
COMMENT ON TABLE users IS 'Все аккаунты: студенты, преподаватели, сотрудники столовой, админы. Роль определяет, какие экраны доступны.';

CREATE TABLE class_schedule (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id     INT NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
    day_of_week  SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),   -- ISO: 1 = понедельник
    starts_at    TIME NOT NULL,
    ends_at      TIME NOT NULL,
    building_id  INT NOT NULL REFERENCES buildings(id),
    subject      VARCHAR(150),
    CHECK (starts_at < ends_at),
    UNIQUE (group_id, day_of_week, starts_at)
);
COMMENT ON TABLE class_schedule IS 'Недельное расписание пар каждой группы. Нужно, чтобы предлагать слоты выдачи только в перемены студента.';

-- ---------- 2.2 Меню и еда ------------------------------------------

CREATE TABLE dish_categories (
    id          SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
COMMENT ON TABLE dish_categories IS 'Супы, вторые блюда, салаты, выпечка, напитки...';

CREATE TABLE dishes (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_id       SMALLINT NOT NULL REFERENCES dish_categories(id),
    name_ru           VARCHAR(120) NOT NULL,
    name_kk           VARCHAR(120),
    description       TEXT,
    base_price        NUMERIC(10,2) NOT NULL CHECK (base_price > 0),   -- в тенге
    portion_grams     SMALLINT CHECK (portion_grams > 0),
    calories          SMALLINT CHECK (calories >= 0),
    protein_g         NUMERIC(5,1),
    fat_g             NUMERIC(5,1),
    carbs_g           NUMERIC(5,1),
    shelf_life_hours  SMALLINT NOT NULL DEFAULT 4 CHECK (shelf_life_hours > 0),   -- срок после приготовления; от него зависят скидки на остатки
    is_halal          BOOLEAN NOT NULL DEFAULT TRUE,
    is_vegetarian     BOOLEAN NOT NULL DEFAULT FALSE,
    photo_url         VARCHAR(255),
    is_active         BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE dishes IS 'Справочник блюд (карточка рецепта). Что продаётся в конкретный день, хранится в menu_items.';

CREATE TABLE ingredients (
    id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  VARCHAR(100) NOT NULL UNIQUE,
    unit  VARCHAR(5) NOT NULL CHECK (unit IN ('g', 'ml', 'pcs'))
);
COMMENT ON TABLE ingredients IS 'Справочник ингредиентов. Повар выбирает из него, аллергены определяются автоматически.';

CREATE TABLE allergens (
    id       SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code     VARCHAR(30) NOT NULL UNIQUE,     -- gluten, milk, eggs, nuts...
    name_ru  VARCHAR(60) NOT NULL,
    name_kk  VARCHAR(60)
);
COMMENT ON TABLE allergens IS 'Фиксированный список аллергенов.';

CREATE TABLE ingredient_allergens (
    ingredient_id  INT NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    allergen_id    SMALLINT NOT NULL REFERENCES allergens(id),
    PRIMARY KEY (ingredient_id, allergen_id)
);
COMMENT ON TABLE ingredient_allergens IS 'Связь M:N. Какие аллергены есть в ингредиенте (мука -> глютен).';

CREATE TABLE dish_ingredients (
    dish_id        INT NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    ingredient_id  INT NOT NULL REFERENCES ingredients(id),
    quantity       NUMERIC(8,2) NOT NULL CHECK (quantity > 0),   -- на одну порцию, в единицах ингредиента
    PRIMARY KEY (dish_id, ingredient_id)
);
COMMENT ON TABLE dish_ingredients IS 'Рецепт, связь M:N. Цепочка блюдо -> ингредиенты -> аллергены даёт список аллергенов любого блюда.';

CREATE TABLE user_allergens (
    user_id      INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    allergen_id  SMALLINT NOT NULL REFERENCES allergens(id),
    severity     allergy_severity NOT NULL DEFAULT 'moderate',
    PRIMARY KEY (user_id, allergen_id)
);
COMMENT ON TABLE user_allergens IS 'Аллергии пользователя (только с согласия). severe = заказ блокируется, иначе предупреждение.';

CREATE TABLE menu_items (
    id                  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canteen_id          INT NOT NULL REFERENCES canteens(id),
    dish_id             INT NOT NULL REFERENCES dishes(id),
    menu_date           DATE NOT NULL,
    price               NUMERIC(10,2) NOT NULL CHECK (price > 0),
    forecast_portions   SMALLINT CHECK (forecast_portions >= 0),   -- прогноз модели, считается утром
    forecast_model      VARCHAR(30),                               -- например, baseline_avg, gbm_v1
    planned_portions    SMALLINT NOT NULL CHECK (planned_portions >= 0),   -- сколько кухня решила приготовить
    available_portions  SMALLINT NOT NULL CHECK (available_portions >= 0), -- живой остаток, который видит студент
    cooked_at           TIMESTAMPTZ,
    UNIQUE (canteen_id, dish_id, menu_date),
    CHECK (available_portions <= planned_portions)
);
COMMENT ON TABLE menu_items IS 'Меню столовой на день: цена, прогноз, план и остаток порций.';

-- ---------- 2.3 Слоты и скидки --------------------------------------

CREATE TABLE pickup_slots (
    id            INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canteen_id    INT NOT NULL REFERENCES canteens(id),
    slot_date     DATE NOT NULL,
    starts_at     TIME NOT NULL,
    ends_at       TIME NOT NULL,
    capacity      SMALLINT NOT NULL CHECK (capacity > 0),
    booked_count  SMALLINT NOT NULL DEFAULT 0 CHECK (booked_count >= 0),
    CHECK (starts_at < ends_at),
    CHECK (booked_count <= capacity),
    UNIQUE (canteen_id, slot_date, starts_at)
);
COMMENT ON TABLE pickup_slots IS 'Окна выдачи заказов. Вместимость ограничивает число заказов на слот, чтобы кухня не захлебнулась.';

CREATE TABLE promotions (
    id                 INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type               promotion_type NOT NULL,
    menu_item_id       INT REFERENCES menu_items(id),       -- leftover: скидка на блюдо
    pickup_slot_id     INT REFERENCES pickup_slots(id),     -- off_peak: скидка на спокойный слот
    discount_percent   SMALLINT NOT NULL CHECK (discount_percent BETWEEN 1 AND 90),
    valid_from         TIMESTAMPTZ NOT NULL,
    valid_to           TIMESTAMPTZ NOT NULL,
    status             promotion_status NOT NULL DEFAULT 'proposed',
    created_by_system  BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by        INT REFERENCES users(id),            -- заведующая подтверждает одной кнопкой
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (valid_from < valid_to),
    CHECK (
        (type = 'leftover' AND menu_item_id IS NOT NULL) OR
        (type = 'off_peak' AND pickup_slot_id IS NOT NULL) OR
        (type = 'loyalty')
    )
);
COMMENT ON TABLE promotions IS 'Скидки: на остатки до того, как испортятся, на спокойные слоты, бонусные. Система предлагает, заведующая подтверждает.';

-- ---------- 2.4 Заказы и оплата -------------------------------------

CREATE TABLE orders (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_number         VARCHAR(10) NOT NULL,              -- короткий номер на наклейке, например A-045
    user_id              INT REFERENCES users(id),           -- NULL для продажи на кассе без предзаказа
    canteen_id           INT NOT NULL REFERENCES canteens(id),
    service_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    pickup_slot_id       INT REFERENCES pickup_slots(id),    -- NULL для продажи на кассе
    channel              order_channel NOT NULL,
    status               order_status NOT NULL DEFAULT 'pending_payment',
    subtotal             NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount_total       NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (discount_total >= 0),
    total                NUMERIC(10,2) GENERATED ALWAYS AS (subtotal - discount_total) STORED,
    qr_token             UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),   -- показывается на выдаче
    allergy_warning_ack  BOOLEAN NOT NULL DEFAULT FALSE,     -- студент подтвердил предупреждение об аллергии
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at              TIMESTAMPTZ,
    ready_at             TIMESTAMPTZ,
    picked_up_at         TIMESTAMPTZ,
    CHECK (discount_total <= subtotal),
    CHECK (channel = 'cashier' OR (user_id IS NOT NULL AND pickup_slot_id IS NOT NULL)),
    UNIQUE (canteen_id, service_date, order_number)
);
COMMENT ON TABLE orders IS 'Заказ. Статусы: pending_payment -> paid -> cooking -> ready -> picked_up (или cancelled / no_show).';

CREATE TABLE order_items (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id         BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id     INT NOT NULL REFERENCES menu_items(id),
    quantity         SMALLINT NOT NULL CHECK (quantity BETWEEN 1 AND 10),
    unit_price       NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),   -- цена на момент заказа
    promotion_id     INT REFERENCES promotions(id),
    discount_amount  NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    UNIQUE (order_id, menu_item_id)
);
COMMENT ON TABLE order_items IS 'Позиции заказа. Цена копируется, чтобы изменение меню не меняло старые заказы.';

CREATE TABLE order_status_history (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id     BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    from_status  order_status,                      -- NULL у первой записи
    to_status    order_status NOT NULL,
    changed_by   INT REFERENCES users(id),          -- повар или кассир; NULL = система
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE order_status_history IS 'Журнал смены статусов, заполняется триггером. Из него считаем время готовки, задержки и долю незабранных заказов.';

CREATE TABLE payments (
    id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id                 BIGINT NOT NULL REFERENCES orders(id),
    method                   payment_method NOT NULL,
    amount                   NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    status                   payment_status NOT NULL DEFAULT 'pending',
    provider_transaction_id  VARCHAR(100) UNIQUE,
    fiscal_receipt_number    VARCHAR(50),      -- номер чека онлайн-кассы (ОФД)
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at             TIMESTAMPTZ
);
COMMENT ON TABLE payments IS 'Попытки оплаты и возвраты. У одного заказа может быть несколько строк (неудачная попытка, потом успешная).';

-- ---------- 2.5 Отзывы и аналитика ----------------------------------

CREATE TABLE notifications (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id      BIGINT REFERENCES orders(id),
    promotion_id  INT REFERENCES promotions(id),
    channel       notification_channel NOT NULL,
    title         VARCHAR(120) NOT NULL,
    body          TEXT NOT NULL,
    sent_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at       TIMESTAMPTZ
);
COMMENT ON TABLE notifications IS 'Уведомления: «заказ готов», скидки на остатки, напоминания перед слотом.';

CREATE TABLE dish_reviews (
    id             INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_item_id  BIGINT NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE CASCADE,
    rating         SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment        TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE dish_reviews IS 'Оценка блюда. Привязана к позиции заказа: оценить может только тот, кто купил, и один раз.';

CREATE TABLE waste_records (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_item_id INT NOT NULL REFERENCES menu_items(id),
    portions     SMALLINT NOT NULL CHECK (portions > 0),
    reason       waste_reason NOT NULL,
    order_id     BIGINT REFERENCES orders(id),     -- обязательно, если заказ не забрали
    recorded_by  INT REFERENCES users(id),
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (reason <> 'uncollected_order' OR order_id IS NOT NULL)
);
COMMENT ON TABLE waste_records IS 'Выброшенные порции. Сравниваем с прогнозом, чтобы посчитать, сколько еды система экономит.';

-- =====================================================================
-- 3. ИНДЕКСЫ (кроме тех, что создаются автоматически для PK и UNIQUE)
-- =====================================================================
CREATE INDEX idx_users_group            ON users (group_id);
CREATE INDEX idx_schedule_group_day     ON class_schedule (group_id, day_of_week);
CREATE INDEX idx_menu_items_day         ON menu_items (canteen_id, menu_date);
CREATE INDEX idx_slots_day              ON pickup_slots (canteen_id, slot_date);
CREATE INDEX idx_orders_user            ON orders (user_id, created_at DESC);
CREATE INDEX idx_orders_slot            ON orders (pickup_slot_id);
CREATE INDEX idx_orders_kitchen_active  ON orders (canteen_id, service_date)
       WHERE status IN ('paid', 'cooking', 'ready');          -- частичный индекс для экрана кухни
CREATE INDEX idx_order_items_order      ON order_items (order_id);
CREATE INDEX idx_order_items_menu       ON order_items (menu_item_id);
CREATE INDEX idx_status_history_order   ON order_status_history (order_id);
CREATE INDEX idx_payments_order         ON payments (order_id);
CREATE INDEX idx_notifications_unread   ON notifications (user_id) WHERE read_at IS NULL;
CREATE INDEX idx_waste_menu_item        ON waste_records (menu_item_id);

-- =====================================================================
-- 4. ТРИГГЕРЫ
-- =====================================================================

-- 4.1 Автоматически заполняем paid_at / ready_at / picked_up_at при смене статуса
CREATE FUNCTION set_order_timestamps() RETURNS trigger AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NEW.status = 'paid'      AND NEW.paid_at      IS NULL THEN NEW.paid_at      := now(); END IF;
        IF NEW.status = 'ready'     AND NEW.ready_at     IS NULL THEN NEW.ready_at     := now(); END IF;
        IF NEW.status = 'picked_up' AND NEW.picked_up_at IS NULL THEN NEW.picked_up_at := now(); END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_timestamps
    BEFORE UPDATE OF status ON orders
    FOR EACH ROW EXECUTE FUNCTION set_order_timestamps();

-- 4.2 Каждая смена статуса пишется в order_status_history.
--     Бэкенд сообщает, кто меняет статус, командой:  SET app.current_user_id = '5';
CREATE FUNCTION log_order_status() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO order_status_history (order_id, from_status, to_status, changed_by)
        VALUES (NEW.id,
                CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END,
                NEW.status,
                NULLIF(current_setting('app.current_user_id', true), '')::INT);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_status_log
    AFTER INSERT OR UPDATE OF status ON orders
    FOR EACH ROW EXECUTE FUNCTION log_order_status();

-- =====================================================================
-- 5. ПРЕДСТАВЛЕНИЯ (VIEW)
-- =====================================================================

-- 5.1 Аллергены каждого блюда, вычисленные из рецепта
CREATE VIEW v_dish_allergens AS
SELECT d.id AS dish_id,
       d.name_ru AS dish,
       COALESCE(string_agg(DISTINCT a.name_ru, ', ' ORDER BY a.name_ru), '') AS allergens
FROM dishes d
LEFT JOIN dish_ingredients di      ON di.dish_id = d.id
LEFT JOIN ingredient_allergens ia  ON ia.ingredient_id = di.ingredient_id
LEFT JOIN allergens a              ON a.id = ia.allergen_id
GROUP BY d.id, d.name_ru;

-- 5.2 Меню на сегодня для приложения студента: остатки, аллергены, действующая скидка
CREATE VIEW v_menu_today AS
SELECT mi.id AS menu_item_id,
       mi.canteen_id,
       dc.name AS category,
       d.name_ru AS dish,
       mi.price,
       p.discount_percent,
       ROUND(mi.price * (100 - COALESCE(p.discount_percent, 0)) / 100, 0) AS price_now,
       mi.available_portions,
       va.allergens
FROM menu_items mi
JOIN dishes d            ON d.id = mi.dish_id
JOIN dish_categories dc  ON dc.id = d.category_id
JOIN v_dish_allergens va ON va.dish_id = d.id
LEFT JOIN promotions p   ON p.menu_item_id = mi.id
                        AND p.type = 'leftover' AND p.status = 'active'
                        AND now() BETWEEN p.valid_from AND p.valid_to
WHERE mi.menu_date = CURRENT_DATE;

-- 5.3 Экран кухни: что собрать, к какому слоту, с пометками об аллергии для наклейки
CREATE VIEW v_kitchen_board AS
SELECT o.canteen_id,
       ps.starts_at AS slot,
       o.order_number,
       o.status,
       string_agg(oi.quantity || ' x ' || d.name_ru, '; ' ORDER BY d.name_ru) AS items,
       (SELECT 'АЛЛЕРГИЯ: ' || string_agg(UPPER(a.name_ru), ', ' ORDER BY a.name_ru)
          FROM user_allergens ua JOIN allergens a ON a.id = ua.allergen_id
         WHERE ua.user_id = o.user_id) AS sticker_flags
FROM orders o
JOIN pickup_slots ps ON ps.id = o.pickup_slot_id
JOIN order_items oi  ON oi.order_id = o.id
JOIN menu_items mi   ON mi.id = oi.menu_item_id
JOIN dishes d        ON d.id = mi.dish_id
WHERE o.service_date = CURRENT_DATE
  AND o.status IN ('paid', 'cooking', 'ready')
GROUP BY o.id, o.canteen_id, ps.starts_at, o.order_number, o.status, o.user_id;

-- =====================================================================
-- 6. ТЕСТОВЫЕ ДАННЫЕ (все даты = сегодня, поэтому представления всегда что-то показывают)
-- =====================================================================

INSERT INTO buildings (name, address) VALUES
    ('Главный корпус', 'Кампус, блок А'),     -- 1
    ('IT-корпус',      'Кампус, блок C');     -- 2

INSERT INTO canteens (building_id, name, opens_at, closes_at, default_slot_minutes, default_slot_capacity) VALUES
    (1, 'Главная столовая', '09:00', '17:00', 10, 30);  -- 1

INSERT INTO student_groups (code, faculty, study_year) VALUES
    ('SE-2301', 'Программная инженерия', 3),   -- 1
    ('SE-2302', 'Программная инженерия', 3),   -- 2
    ('IT-2201', 'Информационные технологии', 4); -- 3

INSERT INTO users (full_name, email, phone, password_hash, role, group_id, canteen_id, preferred_language, health_data_consent_at) VALUES
    ('Аружан Сейтқали',    'aruzhan@uni.kz', '+77010000001', '$2b$12$hash', 'student',         1,    NULL, 'kk', NULL),   -- 1
    ('Данияр Омаров',      'daniyar@uni.kz', '+77010000002', '$2b$12$hash', 'student',         1,    NULL, 'ru', now()),  -- 2 (аллергия на орехи)
    ('Мадина Ахметова',    'madina@uni.kz',  '+77010000003', '$2b$12$hash', 'student',         2,    NULL, 'ru', now()),  -- 3 (аллергия на молоко)
    ('Тимур Беков',        'timur@uni.kz',   '+77010000004', '$2b$12$hash', 'student',         3,    NULL, 'en', NULL),   -- 4
    ('Гульнара Садыкова',  'cook@uni.kz',    '+77010000005', '$2b$12$hash', 'cook',            NULL, 1,    'kk', NULL),   -- 5
    ('Ерлан Жаксыбеков',   'cashier@uni.kz', '+77010000006', '$2b$12$hash', 'cashier',         NULL, 1,    'ru', NULL),   -- 6
    ('Сауле Нурланова',    'manager@uni.kz', '+77010000007', '$2b$12$hash', 'canteen_manager', NULL, 1,    'ru', NULL),   -- 7
    ('Аскар Ибраимов',     'askar@uni.kz',   '+77010000008', '$2b$12$hash', 'teacher',         NULL, NULL, 'ru', NULL),   -- 8
    ('Администратор',      'admin@uni.kz',   NULL,           '$2b$12$hash', 'admin',           NULL, NULL, 'en', NULL);   -- 9

-- Расписание SE-2301 на сегодня: перемены 11:50-12:10 и 13:30-13:40
INSERT INTO class_schedule (group_id, day_of_week, starts_at, ends_at, building_id, subject)
SELECT 1, EXTRACT(ISODOW FROM CURRENT_DATE)::SMALLINT, s, e, 2, subj
FROM (VALUES ('09:00'::TIME, '10:20'::TIME, 'Базы данных'),
             ('10:30',       '11:50',       'DevOps'),
             ('12:10',       '13:30',       'Архитектура ПО'),
             ('13:40',       '15:00',       'Английский язык')) AS t(s, e, subj);

INSERT INTO dish_categories (name, sort_order) VALUES
    ('Супы', 1), ('Вторые блюда', 2), ('Салаты', 3), ('Выпечка и десерты', 4), ('Напитки', 5);

INSERT INTO dishes (category_id, name_ru, name_kk, base_price, portion_grams, calories, protein_g, fat_g, carbs_g, shelf_life_hours, is_vegetarian) VALUES
    (1, 'Куриный суп',   'Тауық сорпасы', 900,  300, 180, 12.0,  6.0, 18.0, 4, FALSE),  -- 1
    (2, 'Лагман',        'Лағман',        1600, 400, 620, 28.0, 22.0, 75.0, 3, FALSE),  -- 2
    (2, 'Плов',          'Палау',         1500, 350, 650, 22.0, 26.0, 80.0, 4, FALSE),  -- 3
    (3, 'Оливье',        'Оливье',        800,  200, 310,  9.0, 24.0, 14.0, 6, FALSE),  -- 4
    (3, 'Овощной салат', 'Көкөніс салаты',600,  200,  90,  2.0,  5.0,  9.0, 4, TRUE),   -- 5
    (4, 'Самса',         'Самса',         450,  150, 380, 14.0, 20.0, 36.0, 6, FALSE),  -- 6
    (4, 'Медовик',       'Бал торты',     700,  120, 420,  6.0, 22.0, 50.0, 24, TRUE),  -- 7
    (5, 'Чай с молоком', 'Сүтті шай',     250,  250,  70,  3.0,  3.0,  8.0, 2, TRUE),   -- 8
    (5, 'Компот',        'Компот',        300,  250, 110,  0.0,  0.0, 27.0, 8, TRUE);   -- 9

INSERT INTO ingredients (name, unit) VALUES
    ('мука пшеничная', 'g'), ('говядина', 'g'), ('курица', 'g'), ('рис', 'g'), ('морковь', 'g'),   -- 1-5
    ('лук', 'g'), ('картофель', 'g'), ('яйцо', 'pcs'), ('молоко', 'ml'), ('сливочное масло', 'g'),  -- 6-10
    ('майонез', 'g'), ('грецкий орех', 'g'), ('мёд', 'g'), ('помидор', 'g'), ('огурец', 'g'),  -- 11-15
    ('чёрный чай', 'g'), ('сухофрукты', 'g'), ('сахар', 'g'), ('баранина', 'g'), ('колбаса', 'g');  -- 16-20

INSERT INTO allergens (code, name_ru, name_kk) VALUES
    ('gluten',  'Глютен',     'Глютен'),        -- 1
    ('milk',    'Молоко',     'Сүт'),           -- 2
    ('eggs',    'Яйца',       'Жұмыртқа'),      -- 3
    ('nuts',    'Орехи',      'Жаңғақ'),        -- 4
    ('soy',     'Соя',        'Соя'),           -- 5
    ('fish',    'Рыба',       'Балық'),         -- 6
    ('sesame',  'Кунжут',     'Күнжіт'),        -- 7
    ('celery',  'Сельдерей',  'Балдыркөк');     -- 8

INSERT INTO ingredient_allergens (ingredient_id, allergen_id) VALUES
    (1, 1),   -- мука -> глютен
    (8, 3),   -- яйцо -> яйца
    (9, 2),   -- молоко -> молоко
    (10, 2),  -- масло -> молоко
    (11, 3),  -- майонез -> яйца
    (12, 4),  -- грецкий орех -> орехи
    (20, 5);  -- колбаса -> соя

INSERT INTO dish_ingredients (dish_id, ingredient_id, quantity) VALUES
    (1, 3, 80), (1, 7, 60), (1, 5, 20), (1, 6, 15), (1, 1, 20),          -- куриный суп (с лапшой)
    (2, 1, 150), (2, 2, 100), (2, 5, 30), (2, 6, 30), (2, 14, 40),       -- лагман
    (3, 4, 150), (3, 19, 100), (3, 5, 60), (3, 6, 30),                   -- плов
    (4, 7, 70), (4, 8, 1), (4, 11, 30), (4, 20, 40), (4, 5, 20),         -- оливье
    (5, 14, 100), (5, 15, 100),                                          -- овощной салат
    (6, 1, 80), (6, 10, 15), (6, 19, 50), (6, 6, 20),                    -- самса
    (7, 1, 50), (7, 13, 20), (7, 8, 1), (7, 10, 20), (7, 12, 10),        -- медовик
    (8, 16, 3), (8, 9, 50), (8, 18, 5),                                  -- чай с молоком
    (9, 17, 40), (9, 18, 15);                                            -- компот

INSERT INTO user_allergens (user_id, allergen_id, severity) VALUES
    (2, 4, 'severe'),   -- Данияр: орехи
    (3, 2, 'mild');     -- Мадина: молоко

INSERT INTO menu_items (canteen_id, dish_id, menu_date, price, forecast_portions, forecast_model, planned_portions, available_portions, cooked_at) VALUES
    (1, 1, CURRENT_DATE, 900,  60, 'gbm_v1', 60, 60, now()),   -- 1 куриный суп
    (1, 2, CURRENT_DATE, 1600, 85, 'gbm_v1', 90, 90, now()),   -- 2 лагман
    (1, 3, CURRENT_DATE, 1500, 110,'gbm_v1', 110,110, now()),  -- 3 плов
    (1, 4, CURRENT_DATE, 800,  35, 'gbm_v1', 35, 35, now()),   -- 4 оливье
    (1, 5, CURRENT_DATE, 600,  25, 'gbm_v1', 25, 25, now()),   -- 5 овощной салат
    (1, 6, CURRENT_DATE, 450,  120,'gbm_v1', 120,120, now()),  -- 6 самса
    (1, 7, CURRENT_DATE, 700,  30, 'gbm_v1', 30, 30, now()),   -- 7 медовик
    (1, 8, CURRENT_DATE, 250,  150,'gbm_v1', 150,150, now()),  -- 8 чай с молоком
    (1, 9, CURRENT_DATE, 300,  100,'gbm_v1', 100,100, now());  -- 9 компот

INSERT INTO pickup_slots (canteen_id, slot_date, starts_at, ends_at, capacity)
SELECT 1, CURRENT_DATE, s, s + INTERVAL '10 minutes', 30
FROM (VALUES ('11:50'::TIME), ('12:00'), ('12:10'), ('12:20'), ('13:30'), ('13:40')) AS t(s);
-- id слотов: 1 = 11:50, 2 = 12:00, 3 = 12:10, 4 = 12:20, 5 = 13:30, 6 = 13:40

INSERT INTO promotions (type, menu_item_id, pickup_slot_id, discount_percent, valid_from, valid_to, status, created_by_system, approved_by) VALUES
    ('off_peak', NULL, 1, 10, CURRENT_DATE + TIME '08:00', CURRENT_DATE + TIME '12:00', 'active',   TRUE, 7),   -- 1: слот 11:50 дешевле на 10%
    ('leftover', 6,    NULL, 30, CURRENT_DATE + TIME '14:30', CURRENT_DATE + TIME '16:00', 'proposed', TRUE, NULL); -- 2: самса -30%, ждёт подтверждения

-- Заказы (создаются в статусе pending_payment, триггер пишет первую запись в историю)
INSERT INTO orders (order_number, user_id, canteen_id, pickup_slot_id, channel) VALUES
    ('A-001', 1,    1, 2,    'mobile_app'),   -- 1 Аружан, 12:00
    ('A-002', 2,    1, 2,    'mobile_app'),   -- 2 Данияр, 12:00
    ('A-003', 3,    1, 3,    'web_qr'),       -- 3 Мадина, 12:10
    ('A-004', 4,    1, 1,    'mobile_app'),   -- 4 Тимур, 11:50 (скидка на спокойный слот)
    ('A-005', 3,    1, 1,    'mobile_app'),   -- 5 Мадина, 11:50, не придёт
    ('K-001', NULL, 1, NULL, 'cashier');      -- 6 продажа на кассе

INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, promotion_id, discount_amount) VALUES
    (1, 2, 1, 1600, NULL, 0),  (1, 8, 1, 250, NULL, 0),      -- лагман + чай с молоком
    (2, 3, 1, 1500, NULL, 0),  (2, 9, 1, 300, NULL, 0),      -- плов + компот
    (3, 1, 1, 900,  NULL, 0),  (3, 6, 1, 450, NULL, 0),      -- суп + самса
    (4, 3, 1, 1500, 1, 150),   (4, 9, 1, 300, 1, 30),        -- плов + компот, скидка 10%
    (5, 4, 1, 800,  1, 80),                                  -- оливье, скидка 10%
    (6, 6, 2, 450,  NULL, 0),  (6, 9, 1, 300, NULL, 0);      -- 2 самсы + компот

-- Суммы заказов из позиций
UPDATE orders o
SET subtotal       = s.subtotal,
    discount_total = s.discount
FROM (SELECT order_id,
             SUM(quantity * unit_price) AS subtotal,
             SUM(discount_amount)       AS discount
      FROM order_items GROUP BY order_id) s
WHERE s.order_id = o.id;

INSERT INTO payments (order_id, method, amount, status, provider_transaction_id, fiscal_receipt_number, completed_at)
SELECT id, CASE WHEN channel = 'cashier' THEN 'cash' ELSE 'kaspi_qr' END::payment_method,
       total, 'succeeded', CASE WHEN channel = 'cashier' THEN NULL ELSE 'TX-' || id END, 'FR-000' || id, now()
FROM orders;

-- Смена статусов сотрудниками (триггер пишет историю и время)
SET app.current_user_id = '';
UPDATE orders SET status = 'paid';                                     -- все оплачены
SET app.current_user_id = '5';                                         -- повар
UPDATE orders SET status = 'cooking' WHERE id IN (1, 2, 3, 5);
UPDATE orders SET status = 'ready'   WHERE id IN (1, 2, 5);
SET app.current_user_id = '6';                                         -- кассир на выдаче
UPDATE orders SET status = 'picked_up' WHERE id IN (1, 6);
SET app.current_user_id = '';                                          -- система
UPDATE orders SET status = 'no_show' WHERE id = 5;

-- Только для демо: скрипт выполняется за секунду, поэтому раскладываем время как в настоящий обед
UPDATE order_status_history h
SET changed_at = CURRENT_DATE + CASE h.to_status
        WHEN 'pending_payment' THEN TIME '10:40'
        WHEN 'paid'            THEN TIME '10:41'
        WHEN 'cooking'         THEN TIME '11:30'
        WHEN 'ready'           THEN TIME '11:44'
        WHEN 'picked_up'       THEN TIME '12:02'
        WHEN 'no_show'         THEN TIME '12:30'
        ELSE TIME '12:00' END + h.order_id * INTERVAL '1 minute';
UPDATE orders o
SET created_at   = (SELECT MIN(changed_at) FROM order_status_history h WHERE h.order_id = o.id),
    paid_at      = (SELECT changed_at FROM order_status_history h WHERE h.order_id = o.id AND h.to_status = 'paid'),
    ready_at     = (SELECT changed_at FROM order_status_history h WHERE h.order_id = o.id AND h.to_status = 'ready'),
    picked_up_at = (SELECT changed_at FROM order_status_history h WHERE h.order_id = o.id AND h.to_status = 'picked_up');

-- Синхронизируем счётчики (в приложении это делается в транзакции заказа)
UPDATE pickup_slots ps
SET booked_count = (SELECT COUNT(*) FROM orders o
                    WHERE o.pickup_slot_id = ps.id AND o.status NOT IN ('cancelled'));
UPDATE menu_items mi
SET available_portions = mi.planned_portions - COALESCE(
        (SELECT SUM(oi.quantity) FROM order_items oi JOIN orders o ON o.id = oi.order_id
          WHERE oi.menu_item_id = mi.id AND o.status <> 'cancelled'), 0);

INSERT INTO notifications (user_id, order_id, promotion_id, channel, title, body) VALUES
    (1, 1, NULL, 'telegram', 'Заказ A-001 готов', 'Заберите на стойке выдачи, полка 1.'),
    (2, 2, NULL, 'push',     'Заказ A-002 готов', 'Заберите на стойке выдачи, полка 2.'),
    (4, NULL, 1, 'push',     'Слот 11:50 дешевле на 10%', 'Закажите на 11:50 и сэкономьте.');

INSERT INTO dish_reviews (order_item_id, rating, comment) VALUES
    (1, 5, 'Лагман огонь'),
    (2, 4, NULL);

INSERT INTO waste_records (menu_item_id, portions, reason, order_id, recorded_by) VALUES
    (4, 1, 'uncollected_order', 5, 5),   -- оливье Мадины не забрали
    (5, 3, 'expired', NULL, 5);          -- 3 овощных салата испортились

-- =====================================================================
-- 7. ПРИМЕРЫ ЗАПРОСОВ (уберите -- в начале строк и выполните)
-- =====================================================================

-- 7.1 Меню на сегодня для приложения
-- SELECT category, dish, price, price_now, available_portions, allergens FROM v_menu_today ORDER BY category, dish;

-- 7.2 Экран кухни
-- SELECT slot, order_number, status, items, sticker_flags FROM v_kitchen_board ORDER BY slot, order_number;

-- 7.3 Какие блюда сегодняшнего меню опасны для пользователя (Данияр, аллергия на орехи)
-- SELECT DISTINCT d.name_ru AS dish, a.name_ru AS allergen, ua.severity
-- FROM menu_items mi
-- JOIN dishes d                 ON d.id = mi.dish_id
-- JOIN dish_ingredients di      ON di.dish_id = d.id
-- JOIN ingredient_allergens ia  ON ia.ingredient_id = di.ingredient_id
-- JOIN allergens a              ON a.id = ia.allergen_id
-- JOIN user_allergens ua        ON ua.allergen_id = ia.allergen_id AND ua.user_id = 2
-- WHERE mi.menu_date = CURRENT_DATE;

-- 7.4 Свободные слоты, которые попадают в перемену студента (не пересекаются с парами)
-- SELECT ps.starts_at, ps.ends_at, ps.capacity - ps.booked_count AS free_places
-- FROM pickup_slots ps
-- WHERE ps.canteen_id = 1 AND ps.slot_date = CURRENT_DATE AND ps.booked_count < ps.capacity
--   AND NOT EXISTS (
--       SELECT 1 FROM class_schedule cs JOIN users u ON u.group_id = cs.group_id
--       WHERE u.id = 1 AND cs.day_of_week = EXTRACT(ISODOW FROM CURRENT_DATE)
--         AND (ps.starts_at, ps.ends_at) OVERLAPS (cs.starts_at, cs.ends_at))
-- ORDER BY ps.starts_at;

-- 7.5 Прогноз, реальные продажи и списания по каждому блюду
-- SELECT d.name_ru AS dish, mi.forecast_portions AS forecast,
--        COALESCE(SUM(oi.quantity) FILTER (WHERE o.status <> 'cancelled'), 0) AS sold,
--        (SELECT COALESCE(SUM(w.portions), 0) FROM waste_records w WHERE w.menu_item_id = mi.id) AS wasted
-- FROM menu_items mi
-- JOIN dishes d ON d.id = mi.dish_id
-- LEFT JOIN order_items oi ON oi.menu_item_id = mi.id
-- LEFT JOIN orders o ON o.id = oi.order_id
-- WHERE mi.menu_date = CURRENT_DATE
-- GROUP BY mi.id, d.name_ru, mi.forecast_portions
-- ORDER BY dish;

-- 7.6 Доля незабранных предзаказов
-- SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'no_show') / NULLIF(COUNT(*), 0), 1) AS no_show_percent
-- FROM orders WHERE channel <> 'cashier' AND service_date = CURRENT_DATE;

-- 7.7 Среднее время от «готовится» до «готов» (по истории статусов)
-- SELECT AVG(r.changed_at - c.changed_at) AS avg_cooking_time
-- FROM order_status_history c
-- JOIN order_status_history r ON r.order_id = c.order_id AND r.to_status = 'ready'
-- WHERE c.to_status = 'cooking';
