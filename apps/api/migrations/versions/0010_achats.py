"""Achats (J16) : fournisseurs, ingrédients en stock, achats et leurs lignes, grand livre du stock.

Révision : 0010
Créée le : 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

stock_unit = sa.Enum("kg", "l", "piece", name="stock_unit")
purchase_category = sa.Enum(
    "ingredients", "emballages", "energie", "entretien", "materiel", "autre",
    name="purchase_category",
)  # fmt: skip
stock_move_kind = sa.Enum("purchase", "cancel", "inventory", name="stock_move_kind")
# Type déjà créé par la migration 0005 : réutilisé tel quel.
payment_method = postgresql.ENUM(
    "cash", "bankily", "sedad", "bimbank", "bamis", name="payment_method", create_type=False
)
QTY = sa.Numeric(12, 3)


def _now() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "supplier",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("phone", sa.String(8), nullable=True),
        sa.Column("note", sa.String(160), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        _now(),
        sa.CheckConstraint("char_length(name) BETWEEN 2 AND 80", name="supplier_name_length"),
        sa.CheckConstraint("phone IS NULL OR phone ~ '^[234][0-9]{7}$'", name="supplier_phone_mr"),
    )
    op.create_table(
        "ingredient",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("unit", stock_unit, nullable=False),
        sa.Column("stock_qty", QTY, nullable=False, server_default="0"),
        sa.Column("alert_qty", QTY, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 2 AND 60", name="ingredient_name_length"),
        sa.CheckConstraint(
            "stock_qty >= 0 AND stock_qty <= 1000000", name="ingredient_stock_range"
        ),
        sa.CheckConstraint(
            "alert_qty IS NULL OR (alert_qty >= 0 AND alert_qty <= 1000000)",
            name="ingredient_alert_range",
        ),
    )
    op.create_table(
        "purchase",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_day", sa.Date, nullable=False),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("supplier.id"), nullable=True),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("total_mru", sa.Integer, nullable=False),
        sa.Column("note", sa.String(160), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("staff_user.id"), nullable=False),
        _now(),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Integer, sa.ForeignKey("staff_user.id"), nullable=True),
        sa.Column("cancel_reason", sa.String(160), nullable=True),
        sa.CheckConstraint("total_mru BETWEEN 1 AND 10000000", name="purchase_total_range"),
        sa.CheckConstraint(
            "(cancelled_at IS NULL) = (cancel_reason IS NULL)", name="purchase_cancel_reason"
        ),
    )
    op.create_index("ix_purchase_purchase_day", "purchase", ["purchase_day"])
    op.create_index("ix_purchase_supplier_id", "purchase", ["supplier_id"])
    op.create_table(
        "purchase_line",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "purchase_id",
            sa.Integer,
            sa.ForeignKey("purchase.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredient.id"), nullable=True),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("category", purchase_category, nullable=False),
        sa.Column("quantity", QTY, nullable=False),
        sa.Column("amount_mru", sa.Integer, nullable=False),
        sa.CheckConstraint("quantity > 0 AND quantity <= 100000", name="purchase_qty_range"),
        sa.CheckConstraint("amount_mru BETWEEN 1 AND 1000000", name="purchase_amount_range"),
        sa.CheckConstraint(
            "ingredient_id IS NULL OR category = 'ingredients'", name="purchase_line_category"
        ),
    )
    op.create_index("ix_purchase_line_ingredient_id", "purchase_line", ["ingredient_id"])
    op.create_table(
        "stock_move",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredient.id"), nullable=False),
        sa.Column("kind", stock_move_kind, nullable=False),
        sa.Column("delta", QTY, nullable=False),
        sa.Column("stock_after", QTY, nullable=False),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchase.id"), nullable=True),
        sa.Column("reason", sa.String(160), nullable=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("staff_user.id"), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stock_move_ingredient_id", "stock_move", ["ingredient_id"])


def downgrade() -> None:
    op.drop_table("stock_move")
    op.drop_table("purchase_line")
    op.drop_table("purchase")
    op.drop_table("ingredient")
    op.drop_table("supplier")
    for enum in (stock_move_kind, purchase_category, stock_unit):
        enum.drop(op.get_bind(), checkfirst=True)
