"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-12

Tables, constraints and indexes of docs/schema.sql (schema `public`),
plus its triggers and views. Seed data lives in scripts/seed.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql  # noqa: F401

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "allergens",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name_ru", sa.String(length=60), nullable=False),
        sa.Column("name_kk", sa.String(length=60), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("allergens_pkey")),
        sa.UniqueConstraint("code", name=op.f("allergens_code_key")),
    )
    op.create_table(
        "buildings",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("buildings_pkey")),
        sa.UniqueConstraint("name", name=op.f("buildings_name_key")),
    )
    op.create_table(
        "dish_categories",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("dish_categories_pkey")),
        sa.UniqueConstraint("name", name=op.f("dish_categories_name_key")),
    )
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=5), nullable=False),
        sa.CheckConstraint("unit IN ('g', 'ml', 'pcs')", name=op.f("ingredients_unit_check")),
        sa.PrimaryKeyConstraint("id", name=op.f("ingredients_pkey")),
        sa.UniqueConstraint("name", name=op.f("ingredients_name_key")),
    )
    op.create_table(
        "student_groups",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("faculty", sa.String(length=100), nullable=True),
        sa.Column("study_year", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint(
            "study_year BETWEEN 1 AND 6", name=op.f("student_groups_study_year_check")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("student_groups_pkey")),
        sa.UniqueConstraint("code", name=op.f("student_groups_code_key")),
    )
    op.create_table(
        "canteens",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("default_slot_minutes", sa.SmallInteger(), server_default="10", nullable=False),
        sa.Column("default_slot_capacity", sa.SmallInteger(), server_default="30", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "default_slot_capacity > 0", name=op.f("canteens_default_slot_capacity_check")
        ),
        sa.CheckConstraint(
            "default_slot_minutes BETWEEN 5 AND 60",
            name=op.f("canteens_default_slot_minutes_check"),
        ),
        sa.CheckConstraint("opens_at < closes_at", name=op.f("canteens_hours_check")),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], name=op.f("canteens_building_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("canteens_pkey")),
    )
    op.create_table(
        "class_schedule",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=150), nullable=True),
        sa.CheckConstraint(
            "day_of_week BETWEEN 1 AND 7", name=op.f("class_schedule_day_of_week_check")
        ),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("class_schedule_times_check")),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], name=op.f("class_schedule_building_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["student_groups.id"],
            name=op.f("class_schedule_group_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("class_schedule_pkey")),
        sa.UniqueConstraint(
            "group_id",
            "day_of_week",
            "starts_at",
            name=op.f("class_schedule_group_id_day_of_week_starts_at_key"),
        ),
    )
    op.create_index(
        "idx_schedule_group_day", "class_schedule", ["group_id", "day_of_week"], unique=False
    )
    op.create_table(
        "dishes",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("name_kk", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("portion_grams", sa.SmallInteger(), nullable=True),
        sa.Column("calories", sa.SmallInteger(), nullable=True),
        sa.Column("protein_g", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("fat_g", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("carbs_g", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("shelf_life_hours", sa.SmallInteger(), server_default="4", nullable=False),
        sa.Column("is_halal", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_vegetarian", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("photo_url", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("base_price > 0", name=op.f("dishes_base_price_check")),
        sa.CheckConstraint("calories >= 0", name=op.f("dishes_calories_check")),
        sa.CheckConstraint("portion_grams > 0", name=op.f("dishes_portion_grams_check")),
        sa.CheckConstraint("shelf_life_hours > 0", name=op.f("dishes_shelf_life_hours_check")),
        sa.ForeignKeyConstraint(
            ["category_id"], ["dish_categories.id"], name=op.f("dishes_category_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("dishes_pkey")),
    )
    op.create_table(
        "ingredient_allergens",
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("allergen_id", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["allergen_id"], ["allergens.id"], name=op.f("ingredient_allergens_allergen_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"],
            ["ingredients.id"],
            name=op.f("ingredient_allergens_ingredient_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "ingredient_id", "allergen_id", name=op.f("ingredient_allergens_pkey")
        ),
    )
    op.create_table(
        "dish_ingredients",
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("dish_ingredients_quantity_check")),
        sa.ForeignKeyConstraint(
            ["dish_id"],
            ["dishes.id"],
            name=op.f("dish_ingredients_dish_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredients.id"], name=op.f("dish_ingredients_ingredient_id_fkey")
        ),
        sa.PrimaryKeyConstraint("dish_id", "ingredient_id", name=op.f("dish_ingredients_pkey")),
    )
    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("canteen_id", sa.Integer(), nullable=False),
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("menu_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("forecast_portions", sa.SmallInteger(), nullable=True),
        sa.Column("forecast_model", sa.String(length=30), nullable=True),
        sa.Column("planned_portions", sa.SmallInteger(), nullable=False),
        sa.Column("available_portions", sa.SmallInteger(), nullable=False),
        sa.Column("cooked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "available_portions <= planned_portions",
            name=op.f("menu_items_available_le_planned_check"),
        ),
        sa.CheckConstraint(
            "available_portions >= 0", name=op.f("menu_items_available_portions_check")
        ),
        sa.CheckConstraint(
            "forecast_portions >= 0", name=op.f("menu_items_forecast_portions_check")
        ),
        sa.CheckConstraint("planned_portions >= 0", name=op.f("menu_items_planned_portions_check")),
        sa.CheckConstraint("price > 0", name=op.f("menu_items_price_check")),
        sa.ForeignKeyConstraint(
            ["canteen_id"], ["canteens.id"], name=op.f("menu_items_canteen_id_fkey")
        ),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"], name=op.f("menu_items_dish_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("menu_items_pkey")),
        sa.UniqueConstraint(
            "canteen_id",
            "dish_id",
            "menu_date",
            name=op.f("menu_items_canteen_id_dish_id_menu_date_key"),
        ),
    )
    op.create_index("idx_menu_items_day", "menu_items", ["canteen_id", "menu_date"], unique=False)
    op.create_table(
        "pickup_slots",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("canteen_id", sa.Integer(), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("capacity", sa.SmallInteger(), nullable=False),
        sa.Column("booked_count", sa.SmallInteger(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "booked_count <= capacity", name=op.f("pickup_slots_booked_le_capacity_check")
        ),
        sa.CheckConstraint("booked_count >= 0", name=op.f("pickup_slots_booked_count_check")),
        sa.CheckConstraint("capacity > 0", name=op.f("pickup_slots_capacity_check")),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("pickup_slots_times_check")),
        sa.ForeignKeyConstraint(
            ["canteen_id"], ["canteens.id"], name=op.f("pickup_slots_canteen_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pickup_slots_pkey")),
        sa.UniqueConstraint(
            "canteen_id",
            "slot_date",
            "starts_at",
            name=op.f("pickup_slots_canteen_id_slot_date_starts_at_key"),
        ),
    )
    op.create_index("idx_slots_day", "pickup_slots", ["canteen_id", "slot_date"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "student",
                "teacher",
                "cook",
                "cashier",
                "canteen_manager",
                "admin",
                name="user_role",
            ),
            server_default="student",
            nullable=False,
        ),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("canteen_id", sa.Integer(), nullable=True),
        sa.Column("preferred_language", sa.CHAR(length=2), server_default="ru", nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("health_data_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loyalty_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "preferred_language IN ('kk', 'ru', 'en')", name=op.f("users_preferred_language_check")
        ),
        sa.CheckConstraint(
            "role <> 'student' OR group_id IS NOT NULL", name=op.f("users_student_group_check")
        ),
        sa.CheckConstraint(
            "role NOT IN ('cook', 'cashier', 'canteen_manager') OR canteen_id IS NOT NULL",
            name=op.f("users_staff_canteen_check"),
        ),
        sa.CheckConstraint("loyalty_points >= 0", name=op.f("users_loyalty_points_check")),
        sa.ForeignKeyConstraint(
            ["canteen_id"], ["canteens.id"], name=op.f("users_canteen_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["student_groups.id"], name=op.f("users_group_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("users_pkey")),
        sa.UniqueConstraint("email", name=op.f("users_email_key")),
        sa.UniqueConstraint("phone", name=op.f("users_phone_key")),
        sa.UniqueConstraint("telegram_chat_id", name=op.f("users_telegram_chat_id_key")),
    )
    op.create_index("idx_users_group", "users", ["group_id"], unique=False)
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("order_number", sa.String(length=10), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("canteen_id", sa.Integer(), nullable=False),
        sa.Column(
            "service_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False
        ),
        sa.Column("pickup_slot_id", sa.Integer(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("mobile_app", "web_qr", "cashier", name="order_channel"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending_payment",
                "paid",
                "cooking",
                "ready",
                "picked_up",
                "cancelled",
                "no_show",
                name="order_status",
            ),
            server_default="pending_payment",
            nullable=False,
        ),
        sa.Column(
            "subtotal", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "discount_total", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "total",
            sa.Numeric(precision=10, scale=2),
            sa.Computed("subtotal - discount_total", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "qr_token", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "allergy_warning_ack", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel = 'cashier' OR (user_id IS NOT NULL AND pickup_slot_id IS NOT NULL)",
            name=op.f("orders_channel_owner_check"),
        ),
        sa.CheckConstraint(
            "discount_total <= subtotal", name=op.f("orders_discount_le_subtotal_check")
        ),
        sa.CheckConstraint("discount_total >= 0", name=op.f("orders_discount_total_check")),
        sa.CheckConstraint("subtotal >= 0", name=op.f("orders_subtotal_check")),
        sa.ForeignKeyConstraint(
            ["canteen_id"], ["canteens.id"], name=op.f("orders_canteen_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["pickup_slot_id"], ["pickup_slots.id"], name=op.f("orders_pickup_slot_id_fkey")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("orders_user_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("orders_pkey")),
        sa.UniqueConstraint(
            "canteen_id",
            "service_date",
            "order_number",
            name=op.f("orders_canteen_id_service_date_order_number_key"),
        ),
        sa.UniqueConstraint("qr_token", name=op.f("orders_qr_token_key")),
    )
    op.create_index(
        "idx_orders_kitchen_active",
        "orders",
        ["canteen_id", "service_date"],
        unique=False,
        postgresql_where=sa.text("status IN ('paid', 'cooking', 'ready')"),
    )
    op.create_index("idx_orders_slot", "orders", ["pickup_slot_id"], unique=False)
    op.create_index(
        "idx_orders_user", "orders", ["user_id", sa.literal_column("created_at DESC")], unique=False
    )
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum("leftover", "off_peak", "loyalty", name="promotion_type"),
            nullable=False,
        ),
        sa.Column("menu_item_id", sa.Integer(), nullable=True),
        sa.Column("pickup_slot_id", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.SmallInteger(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("proposed", "active", "rejected", "expired", name="promotion_status"),
            server_default="proposed",
            nullable=False,
        ),
        sa.Column(
            "created_by_system", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(type = 'leftover' AND menu_item_id IS NOT NULL) OR (type = 'off_peak' AND pickup_slot_id IS NOT NULL) OR (type = 'loyalty')",
            name=op.f("promotions_target_check"),
        ),
        sa.CheckConstraint(
            "discount_percent BETWEEN 1 AND 90", name=op.f("promotions_discount_percent_check")
        ),
        sa.CheckConstraint("valid_from < valid_to", name=op.f("promotions_validity_check")),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("promotions_approved_by_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], name=op.f("promotions_menu_item_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["pickup_slot_id"], ["pickup_slots.id"], name=op.f("promotions_pickup_slot_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("promotions_pkey")),
    )
    op.create_table(
        "user_allergens",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("allergen_id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("mild", "moderate", "severe", name="allergy_severity"),
            server_default="moderate",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["allergen_id"], ["allergens.id"], name=op.f("user_allergens_allergen_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("user_allergens_user_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "allergen_id", name=op.f("user_allergens_pkey")),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("promotion_id", sa.Integer(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("push", "telegram", "sms", name="notification_channel"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("notifications_order_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["promotions.id"], name=op.f("notifications_promotion_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("notifications_user_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("notifications_pkey")),
    )
    op.create_index(
        "idx_notifications_unread",
        "notifications",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("promotion_id", sa.Integer(), nullable=True),
        sa.Column(
            "discount_amount", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False
        ),
        sa.CheckConstraint("discount_amount >= 0", name=op.f("order_items_discount_amount_check")),
        sa.CheckConstraint("quantity BETWEEN 1 AND 10", name=op.f("order_items_quantity_check")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("order_items_unit_price_check")),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], name=op.f("order_items_menu_item_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("order_items_order_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"], ["promotions.id"], name=op.f("order_items_promotion_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("order_items_pkey")),
        sa.UniqueConstraint(
            "order_id", "menu_item_id", name=op.f("order_items_order_id_menu_item_id_key")
        ),
    )
    op.create_index("idx_order_items_menu", "order_items", ["menu_item_id"], unique=False)
    op.create_index("idx_order_items_order", "order_items", ["order_id"], unique=False)
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "from_status",
            sa.Enum(
                "pending_payment",
                "paid",
                "cooking",
                "ready",
                "picked_up",
                "cancelled",
                "no_show",
                name="order_status",
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "pending_payment",
                "paid",
                "cooking",
                "ready",
                "picked_up",
                "cancelled",
                "no_show",
                name="order_status",
            ),
            nullable=False,
        ),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"], ["users.id"], name=op.f("order_status_history_changed_by_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("order_status_history_order_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("order_status_history_pkey")),
    )
    op.create_index("idx_status_history_order", "order_status_history", ["order_id"], unique=False)
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "method",
            sa.Enum("kaspi_qr", "bank_card", "cash", name="payment_method"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "succeeded", "failed", "refunded", name="payment_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("provider_transaction_id", sa.String(length=100), nullable=True),
        sa.Column("fiscal_receipt_number", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name=op.f("payments_amount_check")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("payments_order_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("payments_pkey")),
        sa.UniqueConstraint(
            "provider_transaction_id", name=op.f("payments_provider_transaction_id_key")
        ),
    )
    op.create_index("idx_payments_order", "payments", ["order_id"], unique=False)
    op.create_table(
        "waste_records",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("portions", sa.SmallInteger(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum("expired", "uncollected_order", "damaged", "other", name="waste_reason"),
            nullable=False,
        ),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason <> 'uncollected_order' OR order_id IS NOT NULL",
            name=op.f("waste_records_uncollected_order_check"),
        ),
        sa.CheckConstraint("portions > 0", name=op.f("waste_records_portions_check")),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], name=op.f("waste_records_menu_item_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("waste_records_order_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["users.id"], name=op.f("waste_records_recorded_by_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("waste_records_pkey")),
    )
    op.create_index("idx_waste_menu_item", "waste_records", ["menu_item_id"], unique=False)
    op.create_table(
        "dish_reviews",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("dish_reviews_rating_check")),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("dish_reviews_order_item_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("dish_reviews_pkey")),
        sa.UniqueConstraint("order_item_id", name=op.f("dish_reviews_order_item_id_key")),
    )
    op.execute(TRIGGERS_AND_VIEWS)


def downgrade() -> None:
    op.execute(DROP_TRIGGERS_AND_VIEWS)
    op.drop_table("dish_reviews")
    op.drop_index("idx_waste_menu_item", table_name="waste_records")
    op.drop_table("waste_records")
    op.drop_index("idx_payments_order", table_name="payments")
    op.drop_table("payments")
    op.drop_index("idx_status_history_order", table_name="order_status_history")
    op.drop_table("order_status_history")
    op.drop_index("idx_order_items_order", table_name="order_items")
    op.drop_index("idx_order_items_menu", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(
        "idx_notifications_unread",
        table_name="notifications",
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.drop_table("notifications")
    op.drop_table("user_allergens")
    op.drop_table("promotions")
    op.drop_index("idx_orders_user", table_name="orders")
    op.drop_index("idx_orders_slot", table_name="orders")
    op.drop_index(
        "idx_orders_kitchen_active",
        table_name="orders",
        postgresql_where=sa.text("status IN ('paid', 'cooking', 'ready')"),
    )
    op.drop_table("orders")
    op.drop_index("idx_users_group", table_name="users")
    op.drop_table("users")
    op.drop_index("idx_slots_day", table_name="pickup_slots")
    op.drop_table("pickup_slots")
    op.drop_index("idx_menu_items_day", table_name="menu_items")
    op.drop_table("menu_items")
    op.drop_table("dish_ingredients")
    op.drop_table("ingredient_allergens")
    op.drop_table("dishes")
    op.drop_index("idx_schedule_group_day", table_name="class_schedule")
    op.drop_table("class_schedule")
    op.drop_table("canteens")
    op.drop_table("student_groups")
    op.drop_table("ingredients")
    op.drop_table("dish_categories")
    op.drop_table("buildings")
    op.drop_table("allergens")
    for enum_name in ENUM_TYPES:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)


ENUM_TYPES = (
    "user_role",
    "order_status",
    "order_channel",
    "payment_method",
    "payment_status",
    "promotion_type",
    "promotion_status",
    "notification_channel",
    "allergy_severity",
    "waste_reason",
)


# Section 4 and 5 of docs/schema.sql, verbatim apart from the schema prefix.
TRIGGERS_AND_VIEWS = r"""
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

CREATE VIEW v_dish_allergens AS
SELECT d.id AS dish_id,
       d.name_ru AS dish,
       COALESCE(string_agg(DISTINCT a.name_ru, ', ' ORDER BY a.name_ru), '') AS allergens
FROM dishes d
LEFT JOIN dish_ingredients di      ON di.dish_id = d.id
LEFT JOIN ingredient_allergens ia  ON ia.ingredient_id = di.ingredient_id
LEFT JOIN allergens a              ON a.id = ia.allergen_id
GROUP BY d.id, d.name_ru;

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
"""

DROP_TRIGGERS_AND_VIEWS = """
DROP VIEW IF EXISTS v_kitchen_board;
DROP VIEW IF EXISTS v_menu_today;
DROP VIEW IF EXISTS v_dish_allergens;
DROP TRIGGER IF EXISTS trg_orders_status_log ON orders;
DROP TRIGGER IF EXISTS trg_orders_timestamps ON orders;
DROP FUNCTION IF EXISTS log_order_status();
DROP FUNCTION IF EXISTS set_order_timestamps();
"""
