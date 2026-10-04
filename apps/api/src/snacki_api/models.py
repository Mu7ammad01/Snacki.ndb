"""Tables de la base : catalogue (J2), commandes (J3), staff (J6), historique et fidélité (J8)."""

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
    RECUE = "recue"  # créée par le client, à accepter ou refuser par le staff
    ACCEPTEE = "acceptee"  # délai annoncé (et frais de livraison)
    EN_PREPARATION = "en_preparation"
    PRETE = "prete"
    LIVREE = "livree"  # remise au client (retirée au comptoir ou livrée)
    REFUSEE = "refusee"  # refus d'une commande reçue (gérante ou admin)
    ANNULEE = "annulee"  # annulation d'une commande en cours (gérante ou admin)


class OrderSource(enum.StrEnum):
    APP = "app"
    COMPTOIR = "comptoir"


class PaymentMethod(enum.StrEnum):
    CASH = "cash"
    BANKILY = "bankily"
    SEDAD = "sedad"
    BIMBANK = "bimbank"
    BAMIS = "bamis"


class Fulfilment(enum.StrEnum):
    EMPORTER = "emporter"
    LIVRAISON = "livraison"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("service_day", "daily_no", name="uq_orders_day_no"),
        CheckConstraint("total_mru > 0", name="total_positive"),
        CheckConstraint("phone IS NULL OR phone ~ '^[234][0-9]{7}$'", name="phone_mr"),
        CheckConstraint(
            "source = 'comptoir' OR phone IS NOT NULL OR anonymized_at IS NOT NULL",
            name="phone_if_app",
        ),
        CheckConstraint("delivery_fee_mru BETWEEN 0 AND 2000", name="delivery_fee_range"),
        CheckConstraint(
            "discount_mru BETWEEN 0 AND 100 AND discount_mru <= total_mru", name="discount_range"
        ),
        CheckConstraint(
            "fulfilment = 'emporter' OR landmark IS NOT NULL", name="landmark_if_delivery"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_day: Mapped[date] = mapped_column(Date)
    daily_no: Mapped[int]
    customer_name: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str | None] = mapped_column(String(8))  # absent pour une vente au comptoir
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
    # --- Caisse (J7) ---
    source: Mapped[OrderSource] = mapped_column(
        _enum(OrderSource, "order_source"), default=OrderSource.APP, server_default="app"
    )
    note: Mapped[str | None] = mapped_column(String(200))
    pay_pref: Mapped[PaymentMethod | None] = mapped_column(_enum(PaymentMethod, "payment_method"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Frais de livraison fixés par le staff à l'acceptation, jamais par le client (T01).
    delivery_fee_mru: Mapped[int] = mapped_column(default=0, server_default="0")
    customer_called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_method: Mapped[PaymentMethod | None] = mapped_column(
        _enum(PaymentMethod, "payment_method")
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[str | None] = mapped_column(String(160))
    # --- Conservation (J8) : coordonnées effacées après 90 jours, montants conservés ---
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # --- Fidélité (J8 bis) : carte liée à la commande, remise du cadeau (100 MRU au plus) ---
    loyalty_card_id: Mapped[int | None] = mapped_column(ForeignKey("loyalty_card.id"), index=True)
    discount_mru: Mapped[int] = mapped_column(default=0, server_default="0")

    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderLine.id"
    )

    @property
    def grand_total_mru(self) -> int:
        """À payer : articles (prix figés) + frais de livraison − cadeau fidélité."""
        return self.total_mru + self.delivery_fee_mru - self.discount_mru

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


class HistorySale(Base):
    """Vente de l'historique Excel (avant l'app). Montants en MRU ; aucune donnée personnelle."""

    __tablename__ = "history_sale"
    __table_args__ = (
        UniqueConstraint("service_day", "ref", name="uq_history_day_ref"),
        CheckConstraint("total_mru BETWEEN 1 AND 100000", name="history_total_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_day: Mapped[date] = mapped_column(Date, index=True)
    ref: Mapped[str] = mapped_column(String(20))  # « cmd3 » : numéro de la ligne dans l'Excel
    raw_text: Mapped[str] = mapped_column(String(200))
    total_mru: Mapped[int]
    batch: Mapped[str] = mapped_column(String(16))  # empreinte du fichier importé
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list["HistoryItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", order_by="HistoryItem.id"
    )


class HistoryItem(Base):
    """Article reconnu dans le texte d'une vente historique ; produit absent si hors menu."""

    __tablename__ = "history_item"
    __table_args__ = (CheckConstraint("quantity BETWEEN 1 AND 100", name="history_qty_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("history_sale.id", ondelete="CASCADE"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("product.id"))
    label: Mapped[str] = mapped_column(String(60))
    quantity: Mapped[int]

    sale: Mapped[HistorySale] = relationship(back_populates="items")


class CardStatus(enum.StrEnum):
    ISSUED = "issued"  # imprimée, jamais utilisée
    ACTIVE = "active"
    BLOCKED = "blocked"  # perdue, volée ou fraude : plus aucun tampon ni cadeau


class LoyaltyCard(Base):
    """Carte de fidélité. Seules les cartes émises par Snacki existent en base."""

    __tablename__ = "loyalty_card"
    __table_args__ = (
        CheckConstraint("code ~ '^[0-9A-HJKMNP-TV-Z]{8}$'", name="card_code_format"),
        CheckConstraint("stamps BETWEEN 0 AND 100", name="card_stamps_range"),
        CheckConstraint("phone IS NULL OR phone ~ '^[234][0-9]{7}$'", name="card_phone_mr"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)  # 7 caractères aléatoires + contrôle
    status: Mapped[CardStatus] = mapped_column(
        _enum(CardStatus, "card_status"), default=CardStatus.ISSUED
    )
    stamps: Mapped[int] = mapped_column(default=0, server_default="0")
    rewards: Mapped[int] = mapped_column(default=0, server_default="0")
    phone: Mapped[str | None] = mapped_column(String(8), index=True)  # facultatif
    batch: Mapped[str] = mapped_column(String(16))
    blocked_reason: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_stamp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoyaltyKind(enum.StrEnum):
    STAMP = "stamp"
    REVOKE = "revoke"  # commande annulée après le tampon
    REWARD = "reward"
    RESTORE = "restore"  # commande offerte annulée : les tampons reviennent
    TRANSFER = "transfer"  # carte perdue : tampons reportés sur une nouvelle carte


class LoyaltyEvent(Base):
    """Grand livre de la carte : chaque mouvement de tampons, son auteur et sa commande."""

    __tablename__ = "loyalty_event"
    __table_args__ = (
        # Une commande ne donne qu'un tampon et ne paie qu'un cadeau, même en cas de double clic.
        UniqueConstraint("order_id", "kind", name="uq_loyalty_order_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("loyalty_card.id"), index=True)
    kind: Mapped[LoyaltyKind] = mapped_column(_enum(LoyaltyKind, "loyalty_kind"))
    delta: Mapped[int]
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("staff_user.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
