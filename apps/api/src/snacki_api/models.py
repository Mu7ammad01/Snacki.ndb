"""Tables de la base. J2 : le catalogue. J3 : les commandes. J6 : le staff et le journal d'audit."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
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


class StaffRole(enum.StrEnum):
    CAISSIER = "caissier"  # caisse : commandes du jour, encaissement
    GERANTE = "gerante"  # + annulations, prix, pilotage
    ADMIN = "admin"  # + gestion de l'équipe


class StaffUser(Base):
    """Membre du staff. Seules les adresses de cette table peuvent se connecter (liste blanche)."""

    __tablename__ = "staff_user"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("session_version >= 1", name="session_version_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    role: Mapped[StaffRole] = mapped_column(_enum(StaffRole, "staff_role"))
    active: Mapped[bool] = mapped_column(default=True)
    # Augmenté à chaque déconnexion, changement de rôle ou désactivation : toutes les sessions
    # ouvertes deviennent invalides à la requête suivante (T12).
    session_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    """Journal d'audit : qui a fait quoi, quand. L'API n'a aucune route pour le modifier (T11)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("staff_user.id"))
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict | None] = mapped_column(JSON)
