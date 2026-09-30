"""Tables de la base. J2 : le catalogue. J3 : les commandes et leurs lignes."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


def _enum(cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class OrderStatus(enum.StrEnum):
    RECUE = "recue"  # créée par le client, à confirmer par le staff (J7)
    EN_PREPARATION = "en_preparation"
    PRETE = "prete"
    LIVREE = "livree"
    ANNULEE = "annulee"


class Fulfilment(enum.StrEnum):
    EMPORTER = "emporter"
    LIVRAISON = "livraison"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("service_day", "daily_no", name="uq_orders_day_no"),
        CheckConstraint("total_mru > 0", name="total_positive"),
        CheckConstraint("phone ~ '^[234][0-9]{7}$'", name="phone_mr"),
        CheckConstraint(
            "fulfilment = 'emporter' OR landmark IS NOT NULL", name="landmark_if_delivery"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_day: Mapped[date] = mapped_column(Date)
    daily_no: Mapped[int]
    customer_name: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str] = mapped_column(String(8))
    fulfilment: Mapped[Fulfilment] = mapped_column(_enum(Fulfilment, "fulfilment"))
    landmark: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus, "order_status"), default=OrderStatus.RECUE
    )
    # Calculé par l'API à partir des prix en base, jamais reçu du client (menace T01).
    total_mru: Mapped[int]
    # Empreinte SHA-256 du jeton de suivi : le jeton lui-même n'est jamais stocké (T02).
    tracking_hash: Mapped[str] = mapped_column(String(64), unique=True)
    tracking_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderLine.id"
    )

    @property
    def number(self) -> str:
        """Numéro lisible, attribué par le serveur : SNK-MMJJ-001, SNK-MMJJ-002…"""
        return f"SNK-{self.service_day:%m%d}-{self.daily_no:03d}"


class OrderLine(Base):
    __tablename__ = "order_line"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_line_product"),
        CheckConstraint("quantity BETWEEN 1 AND 20", name="quantity_range"),
        CheckConstraint("unit_price_mru > 0", name="unit_price_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"))
    quantity: Mapped[int]
    # Prix copié au moment de la vente : l'historique ne change pas si le prix change.
    unit_price_mru: Mapped[int]

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()

    @property
    def line_total_mru(self) -> int:
        return self.quantity * self.unit_price_mru
