"""Catalogue : table des produits.

Révision : 0001
Créée le : 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

category = sa.Enum("jus", "delices", name="category")
badge = sa.Enum("top", "pop", name="badge")


def upgrade() -> None:
    op.create_table(
        "product",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("category", category, nullable=False),
        sa.Column("name_fr", sa.String(60), nullable=False),
        sa.Column("name_ar", sa.String(60), nullable=False),
        sa.Column("description_fr", sa.String(160), nullable=False),
        sa.Column("description_ar", sa.String(160), nullable=False),
        sa.Column("price_mru", sa.Integer, nullable=False),
        sa.Column("available", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("badge", badge, nullable=True),
        sa.Column("photo", sa.String(120), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("price_mru > 0 AND price_mru <= 10000", name="price_range"),
        sa.CheckConstraint("id ~ '^[a-z][a-z-]{0,39}$'", name="id_slug"),
    )


def downgrade() -> None:
    op.drop_table("product")
    badge.drop(op.get_bind(), checkfirst=True)
    category.drop(op.get_bind(), checkfirst=True)
