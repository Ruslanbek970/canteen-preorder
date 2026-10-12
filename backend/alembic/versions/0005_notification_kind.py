"""notifications: in-app channel and event kind (SPEC 7.11)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every notification is a row in the app's feed; Telegram and Web Push are extra deliveries.
    op.execute("ALTER TYPE notification_channel ADD VALUE IF NOT EXISTS 'in_app'")
    op.add_column("notifications", sa.Column("kind", sa.String(length=30), nullable=True))
    op.create_index(
        "idx_notifications_user_sent", "notifications", ["user_id", sa.text("sent_at DESC")]
    )
    # One reminder per order, even if the job runs twice.
    op.create_index(
        "uq_notifications_order_kind",
        "notifications",
        ["order_id", "kind"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL AND kind IS NOT NULL"),
    )


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value; 'in_app' stays until the type is dropped.
    op.drop_index("uq_notifications_order_kind", table_name="notifications")
    op.drop_index("idx_notifications_user_sent", table_name="notifications")
    op.drop_column("notifications", "kind")
