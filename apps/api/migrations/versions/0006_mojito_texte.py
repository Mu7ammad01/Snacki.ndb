"""Menu : description du mojito sans la mention « sans alcool » (demande de la gérante).

Révision : 0006
Créée le : 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

product = sa.table(
    "product",
    sa.column("id", sa.String),
    sa.column("description_fr", sa.String),
    sa.column("description_ar", sa.String),
)


def _set(fr: str, ar: str) -> None:
    op.execute(
        product.update()
        .where(product.c.id == "mojito")
        .values(description_fr=fr, description_ar=ar)
    )


def upgrade() -> None:
    _set("Menthe et citron vert", "نعناع وليمون")


def downgrade() -> None:
    _set("Menthe et citron vert, sans alcool", "نعناع وليمون، بدون كحول")
