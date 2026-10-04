"""Fidélité : cartes à numéro unique, grand livre des tampons, cadeau sur la commande.

Révision : 0008
Créée le : 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

card_status = sa.Enum("issued", "active", "blocked", name="card_status")
loyalty_kind = sa.Enum("stamp", "revoke", "reward", "restore", "transfer", name="loyalty_kind")


def upgrade() -> None:
    op.create_table(
        "loyalty_card",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        sa.Column("status", card_status, nullable=False),
        sa.Column("stamps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rewards", sa.Integer, nullable=False, server_default="0"),
        sa.Column("phone", sa.String(8), nullable=True),
        sa.Column("batch", sa.String(16), nullable=False),
        sa.Column("blocked_reason", sa.String(160), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_stamp_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("code ~ '^[0-9A-HJKMNP-TV-Z]{8}$'", name="card_code_format"),
        sa.CheckConstraint("stamps BETWEEN 0 AND 100", name="card_stamps_range"),
        sa.CheckConstraint("phone IS NULL OR phone ~ '^[234][0-9]{7}$'", name="card_phone_mr"),
    )
    op.create_index("ix_loyalty_card_phone", "loyalty_card", ["phone"])

    op.add_column("orders", sa.Column("loyalty_card_id", sa.Integer, nullable=True))
    op.create_foreign_key(
        "fk_orders_loyalty_card", "orders", "loyalty_card", ["loyalty_card_id"], ["id"]
    )
    op.create_index("ix_orders_loyalty_card_id", "orders", ["loyalty_card_id"])
    op.add_column(
        "orders", sa.Column("discount_mru", sa.Integer, nullable=False, server_default="0")
    )
    op.create_check_constraint(
        "discount_range", "orders", "discount_mru BETWEEN 0 AND 100 AND discount_mru <= total_mru"
    )

    op.create_table(
        "loyalty_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("card_id", sa.Integer, sa.ForeignKey("loyalty_card.id"), nullable=False),
        sa.Column("kind", loyalty_kind, nullable=False),
        sa.Column("delta", sa.Integer, nullable=False),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("staff_user.id"), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", "kind", name="uq_loyalty_order_kind"),
    )
    op.create_index("ix_loyalty_event_card_id", "loyalty_event", ["card_id"])


def downgrade() -> None:
    op.drop_index("ix_loyalty_event_card_id", table_name="loyalty_event")
    op.drop_table("loyalty_event")
    op.drop_constraint("discount_range", "orders", type_="check")
    op.drop_column("orders", "discount_mru")
    op.drop_index("ix_orders_loyalty_card_id", table_name="orders")
    op.drop_constraint("fk_orders_loyalty_card", "orders", type_="foreignkey")
    op.drop_column("orders", "loyalty_card_id")
    op.drop_index("ix_loyalty_card_phone", table_name="loyalty_card")
    op.drop_table("loyalty_card")
    sa.Enum(name="loyalty_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="card_status").drop(op.get_bind(), checkfirst=True)
