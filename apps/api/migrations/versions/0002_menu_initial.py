"""Menu initial : les 9 produits du menu imprimé, prix en MRU (décision du 25/09/2026).

Révision : 0002
Précédente : 0001
Créée le : 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MENU = [
    # id, catégorie, nom FR, nom AR, description FR, description AR, prix, badge
    ("salade", "delices", "Salade de fruits", "صلاد فروي",
     "Pomme, poire, raisin, dattes, banane, crème d’avocat",
     "تفاح، إجاص، عنب، تمر، موز مع كريمة الأفوكا", 100, "top"),
    ("crepe", "delices", "Crêpe", "اكريب", "Chocolat et banane", "شوكولاتة وموز", 120, "pop"),
    ("avocat", "jus", "Jus avocat", "عصير أفوكا", "Avocat mixé au lait", "أفوكا بالحليب", 100, "pop"),
    ("fraise", "jus", "Jus fraise", "عصير الفراولة", "Fraises mixées au lait", "فراولة بالحليب",
     100, None),
    ("mangue", "jus", "Jus mangue", "عصير مانكو", "Mangue bien fraîche", "مانكو بارد", 100, None),
    ("orange", "jus", "Jus orange", "عصير البرتقال", "Oranges pressées", "برتقال معصور", 100, None),
    ("cocktail", "jus", "Jus cocktail", "عصير كوكتيل", "Mélange de fruits", "خليط فواكه", 100, None),
    ("banane-fraise", "jus", "Jus banane-fraise", "عصير بنانة والفراولة", "Banane et fraise",
     "موز وفراولة", 100, None),
    ("mojito", "jus", "Mojito", "موخيتو", "Menthe et citron vert, sans alcool",
     "نعناع وليمون، بدون كحول", 100, None),
]  # fmt: skip

product = sa.table(
    "product",
    sa.column("id", sa.String),
    sa.column("category", ENUM(name="category", create_type=False)),
    sa.column("name_fr", sa.String),
    sa.column("name_ar", sa.String),
    sa.column("description_fr", sa.String),
    sa.column("description_ar", sa.String),
    sa.column("price_mru", sa.Integer),
    sa.column("position", sa.Integer),
    sa.column("badge", ENUM(name="badge", create_type=False)),
    sa.column("photo", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(
        product,
        [
            {
                "id": pid,
                "category": cat,
                "name_fr": nfr,
                "name_ar": nar,
                "description_fr": dfr,
                "description_ar": dar,
                "price_mru": price,
                "position": pos,
                "badge": badge,
                "photo": f"img/{pid}.jpg",
            }
            for pos, (pid, cat, nfr, nar, dfr, dar, price, badge) in enumerate(MENU)
        ],  # fmt: skip
    )


def downgrade() -> None:
    op.execute(product.delete().where(product.c.id.in_([row[0] for row in MENU])))
