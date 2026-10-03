"""Caisse : statuts acceptée et refusée, ventes au comptoir, délai, frais, paiement.

Révision : 0005
Créée le : 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

order_source = sa.Enum("app", "comptoir", name="order_source")
payment_method = sa.Enum("cash", "bankily", "sedad", "bimbank", "bamis", name="payment_method")
OLD_STATUSES = ("recue", "en_preparation", "prete", "livree", "annulee")


def upgrade() -> None:
    # PostgreSQL ajoute une valeur à un type énuméré sans réécrire la table.
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'acceptee' AFTER 'recue'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'refusee' AFTER 'livree'")
    bind = op.get_bind()
    order_source.create(bind, checkfirst=True)
    payment_method.create(bind, checkfirst=True)

    op.add_column("orders", sa.Column("source", order_source, nullable=False, server_default="app"))
    op.add_column("orders", sa.Column("note", sa.String(200), nullable=True))
    op.add_column("orders", sa.Column("pay_pref", payment_method, nullable=True))
    op.add_column("orders", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "orders", sa.Column("delivery_fee_mru", sa.Integer, nullable=False, server_default="0")
    )
    op.add_column(
        "orders", sa.Column("customer_called_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("orders", sa.Column("paid_method", payment_method, nullable=True))
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("closed_reason", sa.String(160), nullable=True))

    # Une vente au comptoir n'a pas forcément de téléphone ; une commande de l'app, toujours.
    op.alter_column("orders", "phone", existing_type=sa.String(8), nullable=True)
    op.drop_constraint("phone_mr", "orders", type_="check")
    op.create_check_constraint("phone_mr", "orders", "phone IS NULL OR phone ~ '^[234][0-9]{7}$'")
    op.create_check_constraint("phone_if_app", "orders", "source = 'comptoir' OR phone IS NOT NULL")
    op.create_check_constraint(
        "delivery_fee_range", "orders", "delivery_fee_mru BETWEEN 0 AND 2000"
    )


def downgrade() -> None:
    op.execute("DELETE FROM orders WHERE source = 'comptoir'")
    op.drop_constraint("delivery_fee_range", "orders", type_="check")
    op.drop_constraint("phone_if_app", "orders", type_="check")
    op.drop_constraint("phone_mr", "orders", type_="check")
    op.create_check_constraint("phone_mr", "orders", "phone ~ '^[234][0-9]{7}$'")
    op.alter_column("orders", "phone", existing_type=sa.String(8), nullable=False)
    for column in (
        "closed_reason",
        "paid_at",
        "paid_method",
        "customer_called_at",
        "delivery_fee_mru",
        "ready_at",
        "accepted_at",
        "pay_pref",
        "note",
        "source",
    ):
        op.drop_column("orders", column)
    bind = op.get_bind()
    payment_method.drop(bind, checkfirst=True)
    order_source.drop(bind, checkfirst=True)

    # PostgreSQL ne sait pas retirer une valeur d'un type énuméré : on recrée le type.
    op.execute("UPDATE orders SET status = 'en_preparation' WHERE status = 'acceptee'")
    op.execute("UPDATE orders SET status = 'annulee' WHERE status = 'refusee'")
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE order_status RENAME TO order_status_j7")
    values = ", ".join(f"'{v}'" for v in OLD_STATUSES)
    op.execute(f"CREATE TYPE order_status AS ENUM ({values})")
    op.execute(
        "ALTER TABLE orders ALTER COLUMN status TYPE order_status USING status::text::order_status"
    )
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'recue'")
    op.execute("DROP TYPE order_status_j7")
