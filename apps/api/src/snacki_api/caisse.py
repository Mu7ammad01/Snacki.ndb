"""Caisse (J7) : commandes du jour, cycle de vie, vente au comptoir, encaissement.

Le cycle d'une commande est une machine à états appliquée par l'API (ASVS V2.3.1) : une
transition absente du tableau est refusée (409), quel que soit l'écran qui la demande.
Chaque action est inscrite au journal d'audit avec son auteur (T11).

    reçue ──accepter──▶ acceptée ──▶ en préparation ──▶ prête ──▶ remise
      │                    │               │              │
      └─refuser            └───────────── annuler ────────┘      (gérante ou admin)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from snacki_api import orders, staff
from snacki_api.models import (
    Fulfilment,
    Order,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    StaffRole,
    StaffUser,
)
from snacki_api.schemas import CounterOrderIn

S = OrderStatus
# Transitions « normales », permises à tout le staff.
FORWARD: dict[OrderStatus, OrderStatus] = {
    S.ACCEPTEE: S.EN_PREPARATION,
    S.EN_PREPARATION: S.PRETE,
    S.PRETE: S.LIVREE,
}
OPEN = {S.RECUE, S.ACCEPTEE, S.EN_PREPARATION, S.PRETE}
CLOSED = {S.LIVREE, S.REFUSEE, S.ANNULEE}
MANAGERS = (StaffRole.GERANTE, StaffRole.ADMIN)


class CaisseError(Exception):
    """Action impossible dans l'état actuel de la commande (409)."""


def today_orders(session: Session) -> list[Order]:
    day = datetime.now(UTC).date()
    return list(
        session.scalars(
            select(Order)
            .options(selectinload(Order.lines))
            .where(Order.service_day == day)
            .order_by(Order.daily_no.desc())
        )
    )


def locked(session: Session, order_id: int) -> Order | None:
    """Commande verrouillée pendant l'action : deux caissiers ne la modifient pas en même temps."""
    return session.scalars(
        select(Order)
        .options(selectinload(Order.lines))
        .where(Order.id == order_id)
        .with_for_update(of=Order)
    ).one_or_none()


def _log(session: Session, actor: StaffUser, action: str, order: Order, **detail) -> None:
    staff.audit(session, action, actor, order.number, detail or None)


def accept(
    session: Session, actor: StaffUser, order: Order, ready_in_min: int, fee: int | None
) -> None:
    if order.status != S.RECUE:
        raise CaisseError("Seule une commande reçue peut être acceptée")
    if order.fulfilment is Fulfilment.LIVRAISON and fee is None:
        raise CaisseError("Indiquez les frais de livraison")
    if order.fulfilment is Fulfilment.EMPORTER and fee:
        raise CaisseError("Pas de frais de livraison pour une commande à emporter")
    now = datetime.now(UTC)
    order.status = S.ACCEPTEE
    order.accepted_at = now
    order.ready_at = now + timedelta(minutes=ready_in_min)
    order.delivery_fee_mru = fee or 0
    _log(
        session,
        actor,
        "order_accepted",
        order,
        delai_min=ready_in_min,
        frais=order.delivery_fee_mru,
    )


def advance(session: Session, actor: StaffUser, order: Order, target: OrderStatus) -> None:
    if FORWARD.get(order.status) != target:
        raise CaisseError(f"Passage de « {order.status.value} » à « {target.value} » impossible")
    if (
        target == S.LIVREE
        and order.fulfilment is Fulfilment.LIVRAISON
        and not order.customer_called_at
    ):
        # Décision de la gérante : on appelle le client avant de partir livrer.
        raise CaisseError("Appelez le client avant de marquer la livraison")
    before = order.status
    order.status = target
    _log(session, actor, "order_status", order, avant=before.value, après=target.value)


def mark_called(session: Session, actor: StaffUser, order: Order) -> None:
    if order.status not in OPEN - {S.RECUE}:
        raise CaisseError("Le client s'appelle une fois la commande acceptée")
    order.customer_called_at = datetime.now(UTC)
    _log(session, actor, "customer_called", order)


def close(
    session: Session, actor: StaffUser, order: Order, target: OrderStatus, reason: str
) -> None:
    """Refus (commande reçue) ou annulation (commande en cours) : gérante ou admin uniquement."""
    if actor.role not in MANAGERS:  # défense en profondeur : la route l'exige déjà
        raise PermissionError
    if target == S.REFUSEE and order.status != S.RECUE:
        raise CaisseError("Seule une commande reçue peut être refusée ; sinon, annulez-la")
    if target == S.ANNULEE and order.status not in OPEN - {S.RECUE}:
        raise CaisseError("Seule une commande en cours peut être annulée")
    before = order.status
    order.status = target
    order.closed_reason = reason
    _log(
        session,
        actor,
        "order_refused" if target == S.REFUSEE else "order_cancelled",
        order,
        avant=before.value,
        motif=reason,
        deja_payee=order.paid_at is not None,
        montant=order.grand_total_mru,
    )


def pay(session: Session, actor: StaffUser, order: Order, method: PaymentMethod) -> None:
    if order.status in {S.RECUE, S.REFUSEE, S.ANNULEE}:
        raise CaisseError("Encaissement impossible dans cet état")
    if order.paid_at:
        raise CaisseError("Commande déjà encaissée")
    order.paid_method = method
    order.paid_at = datetime.now(UTC)
    _log(session, actor, "order_paid", order, moyen=method.value, montant=order.grand_total_mru)


def counter_sale(session: Session, actor: StaffUser, data: CounterOrderIn) -> Order:
    """Vente au comptoir : déjà acceptée, part directement en préparation."""
    now = datetime.now(UTC)
    order, _token = orders.new_order(
        session,
        data.items,
        source=OrderSource.COMPTOIR,
        customer_name=data.customer_name or "Comptoir",
        phone=None,
        fulfilment=Fulfilment.EMPORTER,
        note=data.note,
        status=S.EN_PREPARATION,
        accepted_at=now,
        paid_method=data.paid_method,
        paid_at=now if data.paid_method else None,
    )
    _log(session, actor, "counter_sale", order, montant=order.grand_total_mru)
    if data.paid_method:
        _log(
            session,
            actor,
            "order_paid",
            order,
            moyen=data.paid_method.value,
            montant=order.grand_total_mru,
        )
    session.commit()
    return order
