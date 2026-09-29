"""Accès aux données. Toutes les requêtes passent par l'ORM : les valeurs sont toujours
envoyées à PostgreSQL comme paramètres liés, jamais collées dans le texte SQL (ASVS V1.2.4)."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from snacki_api.models import Category, Product


def list_menu(session: Session, category: Category | None = None) -> Sequence[Product]:
    query = select(Product).where(Product.available.is_(True))
    if category is not None:
        query = query.where(Product.category == category)
    return session.scalars(query.order_by(Product.position, Product.id)).all()


def get_product(session: Session, product_id: str) -> Product | None:
    return session.scalars(
        select(Product).where(Product.id == product_id, Product.available.is_(True))
    ).one_or_none()
