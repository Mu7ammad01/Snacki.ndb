"""Tables de la base. J2 : le catalogue. Les commandes arrivent à J3."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Category(enum.StrEnum):
    JUS = "jus"
    DELICES = "delices"


class Badge(enum.StrEnum):
    TOP = "top"  # n° 1 des ventes
    POP = "pop"  # populaire


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        # Règles métier aussi dans la base : même un script fautif ne peut pas les violer.
        CheckConstraint("price_mru > 0 AND price_mru <= 10000", name="price_range"),
        CheckConstraint("id ~ '^[a-z][a-z-]{0,39}$'", name="id_slug"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category", values_callable=lambda e: [m.value for m in e])
    )
    name_fr: Mapped[str] = mapped_column(String(60))
    name_ar: Mapped[str] = mapped_column(String(60))
    description_fr: Mapped[str] = mapped_column(String(160))
    description_ar: Mapped[str] = mapped_column(String(160))
    price_mru: Mapped[int]
    available: Mapped[bool] = mapped_column(default=True)
    position: Mapped[int] = mapped_column(default=0)
    badge: Mapped[Badge | None] = mapped_column(
        Enum(Badge, name="badge", values_callable=lambda e: [m.value for m in e])
    )
    photo: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
