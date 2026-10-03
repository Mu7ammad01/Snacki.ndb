"""Staff et journal d'audit : tables staff_user et audit_log.

Révision : 0004
Créée le : 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

staff_role = sa.Enum("caissier", "gerante", "admin", name="staff_role")


def upgrade() -> None:
    op.create_table(
        "staff_user",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=True),
        sa.Column("role", staff_role, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("session_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
        sa.CheckConstraint("session_version >= 1", name="session_version_positive"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("staff_user.id"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("target", sa.String(120), nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("staff_user")
    staff_role.drop(op.get_bind(), checkfirst=True)
