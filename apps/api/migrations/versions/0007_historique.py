"""Pilotage : historique Excel (ventes et articles) et anonymisation des commandes anciennes.

Révision : 0007
Créée le : 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "history_sale",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("service_day", sa.Date, nullable=False),
        sa.Column("ref", sa.String(20), nullable=False),
        sa.Column("raw_text", sa.String(200), nullable=False),
        sa.Column("total_mru", sa.Integer, nullable=False),
        sa.Column("batch", sa.String(16), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("service_day", "ref", name="uq_history_day_ref"),
        sa.CheckConstraint("total_mru BETWEEN 1 AND 100000", name="history_total_range"),
    )
    op.create_index("ix_history_sale_service_day", "history_sale", ["service_day"])
    op.create_table(
        "history_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "sale_id",
            sa.Integer,
            sa.ForeignKey("history_sale.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(40), sa.ForeignKey("product.id"), nullable=True),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.CheckConstraint("quantity BETWEEN 1 AND 100", name="history_qty_range"),
    )

    op.add_column("orders", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("phone_if_app", "orders", type_="check")
    op.create_check_constraint(
        "phone_if_app",
        "orders",
        "source = 'comptoir' OR phone IS NOT NULL OR anonymized_at IS NOT NULL",
    )


def downgrade() -> None:
    # Les commandes anonymisées n'ont plus de téléphone : elles ne respecteraient plus l'ancienne
    # règle. On leur remet un numéro fictif reconnaissable plutôt que de les supprimer.
    op.execute(
        "UPDATE orders SET phone = '20000000' WHERE anonymized_at IS NOT NULL AND phone IS NULL "
        "AND source = 'app'"
    )
    op.drop_constraint("phone_if_app", "orders", type_="check")
    op.create_check_constraint("phone_if_app", "orders", "source = 'comptoir' OR phone IS NOT NULL")
    op.drop_column("orders", "anonymized_at")
    op.drop_table("history_item")
    op.drop_index("ix_history_sale_service_day", table_name="history_sale")
    op.drop_table("history_sale")
