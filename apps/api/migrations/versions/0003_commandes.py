"""Commandes : tables orders et order_line.

Révision : 0003
Créée le : 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

order_status = sa.Enum("recue", "en_preparation", "prete", "livree", "annulee", name="order_status")
fulfilment = sa.Enum("emporter", "livraison", name="fulfilment")


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("service_day", sa.Date, nullable=False),
        sa.Column("daily_no", sa.Integer, nullable=False),
        sa.Column("customer_name", sa.String(40), nullable=False),
        sa.Column("phone", sa.String(8), nullable=False),
        sa.Column("fulfilment", fulfilment, nullable=False),
        sa.Column("landmark", sa.String(120), nullable=True),
        sa.Column("status", order_status, nullable=False, server_default="recue"),
        sa.Column("total_mru", sa.Integer, nullable=False),
        sa.Column("tracking_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("tracking_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("service_day", "daily_no", name="uq_orders_day_no"),
        sa.CheckConstraint("total_mru > 0", name="total_positive"),
        sa.CheckConstraint("phone ~ '^[234][0-9]{7}$'", name="phone_mr"),
        sa.CheckConstraint(
            "fulfilment = 'emporter' OR landmark IS NOT NULL", name="landmark_if_delivery"
        ),
    )
    op.create_table(
        "order_line",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer,
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(40), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price_mru", sa.Integer, nullable=False),
        sa.UniqueConstraint("order_id", "product_id", name="uq_line_product"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 20", name="quantity_range"),
        sa.CheckConstraint("unit_price_mru > 0", name="unit_price_positive"),
    )


def downgrade() -> None:
    op.drop_table("order_line")
    op.drop_table("orders")
    order_status.drop(op.get_bind(), checkfirst=True)
    fulfilment.drop(op.get_bind(), checkfirst=True)
