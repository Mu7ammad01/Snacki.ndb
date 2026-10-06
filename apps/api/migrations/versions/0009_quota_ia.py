"""Quota d'appels à l'IA par jour et par usage (J10, menace T15).

Révision : 0009
Créée le : 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("feature", sa.String(20), primary_key=True),
        sa.Column("calls", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("calls >= 0", name="ai_usage_calls_positive"),
    )


def downgrade() -> None:
    op.drop_table("ai_usage")
