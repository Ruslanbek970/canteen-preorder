"""SPEC 5.2 changes to schema.sql

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_counters",
        sa.Column("canteen_id", sa.Integer(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("prefix", sa.String(length=2), nullable=False),
        sa.Column("last_value", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["canteen_id"], ["canteens.id"], name=op.f("daily_counters_canteen_id_fkey")
        ),
        sa.PrimaryKeyConstraint(
            "canteen_id", "service_date", "prefix", name=op.f("daily_counters_pkey")
        ),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("refresh_tokens_user_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("refresh_tokens_pkey")),
        sa.UniqueConstraint("token_hash", name=op.f("refresh_tokens_token_hash_key")),
    )
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"], unique=False)

    op.add_column(
        "canteens",
        sa.Column("pickup_shelves_count", sa.SmallInteger(), server_default="10", nullable=False),
    )
    op.add_column(
        "canteens",
        sa.Column("order_cutoff_minutes", sa.SmallInteger(), server_default="15", nullable=False),
    )
    op.add_column("canteens", sa.Column("slug", sa.String(length=50), nullable=True))
    op.create_unique_constraint(op.f("canteens_slug_key"), "canteens", ["slug"])
    op.add_column("orders", sa.Column("pickup_shelf", sa.SmallInteger(), nullable=True))
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Not in SPEC 5.2: PATCH /me needs a stored opt-out of promotional messages (SPEC 7.11, 8.1).
    op.add_column(
        "users",
        sa.Column(
            "marketing_opt_out", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("push_subscriptions_user_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("push_subscriptions_pkey")),
        sa.UniqueConstraint("endpoint", name=op.f("push_subscriptions_endpoint_key")),
    )
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "run_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("model", sa.String(length=30), nullable=False),
        sa.Column("mae", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("mape", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("forecast_runs_pkey")),
    )


def downgrade() -> None:
    op.drop_table("forecast_runs")
    op.drop_table("push_subscriptions")
    op.drop_column("users", "marketing_opt_out")
    op.drop_column("users", "email_verified_at")
    op.drop_column("orders", "pickup_shelf")
    op.drop_constraint(op.f("canteens_slug_key"), "canteens", type_="unique")
    op.drop_column("canteens", "slug")
    op.drop_column("canteens", "order_cutoff_minutes")
    op.drop_column("canteens", "pickup_shelves_count")
    op.drop_index("idx_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("daily_counters")
