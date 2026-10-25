"""Achats, fournisseurs et stock (J16, réunion du 25/10/2026).

La gérante et l'admin ont les mêmes droits (vérifiés par la route ET ici, défense en profondeur).
Règles :
- le total d'un achat est la somme de ses lignes, calculée ici, jamais reçue (comme T01) ;
- un achat n'est jamais modifié ni effacé : on l'annule avec un motif, le stock est repris ;
- chaque variation de stock est écrite dans le grand livre (stock_move) et chaque action dans le
  journal d'audit (T11) ;
- les lignes d'ingrédient sont verrouillées (FOR UPDATE) pendant la mise à jour du stock :
  deux saisies simultanées ne peuvent pas perdre une quantité.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from snacki_api import staff
from snacki_api.caisse import MANAGERS
from snacki_api.models import (
    Ingredient,
    PaymentMethod,
    Purchase,
    PurchaseCategory,
    PurchaseLine,
    StaffUser,
    StockMove,
    StockMoveKind,
    Supplier,
)

LIST_LIMIT = 300
CATEGORY_LABELS = {
    "ingredients": "Ingrédients",
    "emballages": "Emballages",
    "energie": "Énergie (gaz, eau, électricité)",
    "entretien": "Entretien",
    "materiel": "Matériel",
    "autre": "Autre",
}


class AchatError(Exception):
    """Refus métier : le message est montré tel quel à la gérante."""


def _check(actor: StaffUser) -> None:
    if actor.role not in MANAGERS:  # défense en profondeur : la route l'exige déjà
        raise AchatError("Réservé à la gérante et à l'admin")


def _flush_unique(session: Session, message: str) -> None:
    """Un doublon de nom (contrainte unique) devient un refus lisible, sans détail de la base."""
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError:
        raise AchatError(message) from None


# --- Fournisseurs ----------------------------------------------------------------------------


def suppliers(session: Session) -> Sequence[Supplier]:
    return session.scalars(select(Supplier).order_by(Supplier.active.desc(), Supplier.name)).all()


def add_supplier(
    session: Session, actor: StaffUser, name: str, phone: str | None, note: str | None
) -> Supplier:
    _check(actor)
    supplier = Supplier(name=name, phone=phone, note=note)
    session.add(supplier)
    _flush_unique(session, "Un fournisseur porte déjà ce nom")
    staff.audit(session, "supplier_added", actor, name)
    return supplier


def update_supplier(
    session: Session, actor: StaffUser, supplier: Supplier, changes: dict[str, Any]
) -> Supplier:
    _check(actor)
    for key in ("name", "phone", "note", "active"):
        if key in changes:
            setattr(supplier, key, changes[key])
    _flush_unique(session, "Un fournisseur porte déjà ce nom")
    staff.audit(session, "supplier_updated", actor, supplier.name, {"champs": ",".join(changes)})
    return supplier


# --- Ingrédients et stock --------------------------------------------------------------------


def ingredients(session: Session) -> Sequence[Ingredient]:
    return session.scalars(
        select(Ingredient).order_by(Ingredient.active.desc(), Ingredient.name)
    ).all()


def add_ingredient(
    session: Session, actor: StaffUser, name: str, unit: str, alert_qty: Decimal | None
) -> Ingredient:
    _check(actor)
    ingredient = Ingredient(name=name, unit=unit, alert_qty=alert_qty, stock_qty=Decimal(0))
    session.add(ingredient)
    _flush_unique(session, "Un ingrédient porte déjà ce nom")
    staff.audit(session, "ingredient_added", actor, name)
    return ingredient


def update_ingredient(
    session: Session, actor: StaffUser, ingredient: Ingredient, changes: dict[str, Any]
) -> Ingredient:
    """Nom, seuil d'alerte, actif. L'unité ne change pas : le stock perdrait son sens."""
    _check(actor)
    for key in ("name", "alert_qty", "active"):
        if key in changes:
            setattr(ingredient, key, changes[key])
    _flush_unique(session, "Un ingrédient porte déjà ce nom")
    staff.audit(
        session, "ingredient_updated", actor, ingredient.name, {"champs": ",".join(changes)}
    )
    return ingredient


def locked_ingredients(session: Session, ids: set[int]) -> dict[int, Ingredient]:
    rows = session.scalars(
        select(Ingredient).where(Ingredient.id.in_(ids)).order_by(Ingredient.id).with_for_update()
    ).all()
    return {i.id: i for i in rows}


def _move(
    session: Session,
    actor: StaffUser,
    ingredient: Ingredient,
    kind: StockMoveKind,
    delta: Decimal,
    purchase: Purchase | None = None,
    reason: str | None = None,
) -> None:
    after = ingredient.stock_qty + delta
    if after < 0:
        raise AchatError(
            f"Le stock de « {ingredient.name} » deviendrait négatif : faites d'abord l'inventaire"
        )
    ingredient.stock_qty = after
    session.add(
        StockMove(
            ingredient_id=ingredient.id,
            kind=kind,
            delta=delta,
            stock_after=after,
            purchase_id=purchase.id if purchase else None,
            reason=reason,
            actor_id=actor.id,
        )
    )


def inventory(
    session: Session, actor: StaffUser, ingredient_id: int, counted: Decimal, reason: str
) -> Ingredient:
    """Comptage réel : le stock devient la quantité comptée ; l'écart est tracé."""
    _check(actor)
    found = locked_ingredients(session, {ingredient_id}).get(ingredient_id)
    if found is None:
        raise LookupError("Ingrédient introuvable")
    delta = counted - found.stock_qty
    _move(session, actor, found, StockMoveKind.INVENTORY, delta, reason=reason)
    staff.audit(
        session,
        "stock_inventory",
        actor,
        found.name,
        {"compte": str(counted), "ecart": str(delta)},
    )
    return found


def moves(session: Session, ingredient_id: int, limit: int = 50) -> Sequence[StockMove]:
    return session.scalars(
        select(StockMove)
        .where(StockMove.ingredient_id == ingredient_id)
        .order_by(StockMove.at.desc(), StockMove.id.desc())
        .limit(limit)
    ).all()


# --- Achats ----------------------------------------------------------------------------------


def create_purchase(session: Session, actor: StaffUser, data: Any) -> Purchase:
    """Enregistre un achat et ajoute au stock les quantités des lignes d'ingrédient."""
    _check(actor)
    if data.supplier_id is not None:
        supplier = session.get(Supplier, data.supplier_id)
        if supplier is None or not supplier.active:
            raise AchatError("Fournisseur introuvable ou désactivé")
    wanted = {line.ingredient_id for line in data.lines if line.ingredient_id is not None}
    stock = locked_ingredients(session, wanted)
    purchase = Purchase(
        purchase_day=data.purchase_day,
        supplier_id=data.supplier_id,
        payment_method=PaymentMethod(data.payment_method),
        note=data.note,
        created_by=actor.id,
        total_mru=sum(line.amount_mru for line in data.lines),
    )
    for line in data.lines:
        if line.ingredient_id is not None:
            ingredient = stock.get(line.ingredient_id)
            if ingredient is None or not ingredient.active:
                raise AchatError("Ingrédient introuvable ou désactivé")
            label, category = ingredient.name, PurchaseCategory.INGREDIENTS
        else:
            if not line.label:
                raise AchatError("Chaque ligne a besoin d'un ingrédient ou d'un libellé")
            label, category = line.label, PurchaseCategory(line.category)
        purchase.lines.append(
            PurchaseLine(
                ingredient_id=line.ingredient_id,
                label=label,
                category=category,
                quantity=line.quantity,
                amount_mru=line.amount_mru,
            )
        )
    session.add(purchase)
    session.flush()  # identifiant de l'achat, pour le grand livre
    for line in purchase.lines:
        if line.ingredient_id is not None:
            _move(
                session, actor, stock[line.ingredient_id], StockMoveKind.PURCHASE,
                line.quantity, purchase,
            )  # fmt: skip
    staff.audit(
        session,
        "purchase_added",
        actor,
        f"achat {purchase.id}",
        {"montant": purchase.total_mru, "lignes": len(purchase.lines)},
    )
    return purchase


def locked_purchase(session: Session, purchase_id: int) -> Purchase | None:
    return session.scalars(
        select(Purchase)
        .where(Purchase.id == purchase_id)
        .options(selectinload(Purchase.lines))
        .with_for_update()
    ).first()


def cancel_purchase(session: Session, actor: StaffUser, purchase: Purchase, reason: str) -> None:
    """Annule un achat : il reste visible (barré), ses quantités sortent du stock."""
    _check(actor)
    if purchase.cancelled_at is not None:
        raise AchatError("Cet achat est déjà annulé")
    wanted = {line.ingredient_id for line in purchase.lines if line.ingredient_id is not None}
    stock = locked_ingredients(session, wanted)
    for line in purchase.lines:
        if line.ingredient_id is not None:
            _move(
                session, actor, stock[line.ingredient_id], StockMoveKind.CANCEL,
                -line.quantity, purchase, reason,
            )  # fmt: skip
    purchase.cancelled_at = datetime.now(UTC)
    purchase.cancelled_by = actor.id
    purchase.cancel_reason = reason
    staff.audit(
        session,
        "purchase_cancelled",
        actor,
        f"achat {purchase.id}",
        {"montant": purchase.total_mru, "motif": reason},
    )


def _authors(session: Session) -> dict[int, str]:
    return {u.id: u.display_name or u.email for u in session.scalars(select(StaffUser))}


def _out(p: Purchase, authors: dict[int, str]) -> dict[str, Any]:
    return {
        "id": p.id,
        "purchase_day": p.purchase_day,
        "supplier_id": p.supplier_id,
        "supplier": p.supplier.name if p.supplier else None,
        "payment_method": p.payment_method.value,
        "total_mru": p.total_mru,
        "note": p.note,
        "created_by": authors.get(p.created_by, ""),
        "created_at": p.created_at,
        "cancelled_at": p.cancelled_at,
        "cancel_reason": p.cancel_reason,
        "lines": [
            {
                "ingredient_id": line.ingredient_id,
                "label": line.label,
                "category": line.category.value,
                "quantity": line.quantity,
                "amount_mru": line.amount_mru,
            }
            for line in p.lines
        ],
    }


def one(session: Session, purchase_id: int) -> dict[str, Any]:
    """Un achat, relu en base après sa création ou son annulation."""
    session.expire_all()
    p = session.scalars(
        select(Purchase)
        .where(Purchase.id == purchase_id)
        .options(selectinload(Purchase.lines), selectinload(Purchase.supplier))
    ).one()
    return _out(p, _authors(session))


def purchases(
    session: Session, start: date, end: date, supplier_id: int | None = None
) -> dict[str, Any]:
    query = (
        select(Purchase)
        .where(Purchase.purchase_day.between(start, end))
        .options(selectinload(Purchase.lines), selectinload(Purchase.supplier))
        .order_by(Purchase.purchase_day.desc(), Purchase.id.desc())
        .limit(LIST_LIMIT + 1)
    )
    if supplier_id is not None:
        query = query.where(Purchase.supplier_id == supplier_id)
    rows = session.scalars(query).all()
    authors = _authors(session)
    out = [_out(p, authors) for p in rows[:LIST_LIMIT]]
    active = [p for p in out if p["cancelled_at"] is None]
    return {
        "start": start,
        "end": end,
        "purchases": out,
        "total_mru": sum(p["total_mru"] for p in active),
        "truncated": len(rows) > LIST_LIMIT,
    }


# --- Pilotage --------------------------------------------------------------------------------


def spending(session: Session, start: date, end: date) -> dict[str, Any]:
    """Dépenses de la période (achats non annulés), par jour, catégorie et fournisseur."""
    valid = (Purchase.purchase_day.between(start, end), Purchase.cancelled_at.is_(None))
    by_day = session.execute(
        select(Purchase.purchase_day, func.sum(Purchase.total_mru))
        .where(*valid)
        .group_by(Purchase.purchase_day)
        .order_by(Purchase.purchase_day)
    ).all()
    by_category = session.execute(
        select(PurchaseLine.category, func.sum(PurchaseLine.amount_mru))
        .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
        .where(*valid)
        .group_by(PurchaseLine.category)
    ).all()
    by_supplier = session.execute(
        select(Supplier.name, func.count(Purchase.id), func.sum(Purchase.total_mru))
        .select_from(Purchase)
        .outerjoin(Supplier, Purchase.supplier_id == Supplier.id)
        .where(*valid)
        .group_by(Supplier.name)
    ).all()
    total = sum(int(a) for _, a in by_day)
    suppliers_out: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount_mru": 0})
    for name, n, amount in by_supplier:
        row = suppliers_out[name or "Sans fournisseur"]
        row["count"] += int(n)
        row["amount_mru"] += int(amount)
    return {
        "total_mru": total,
        "by_day": [{"day": d, "amount_mru": int(a)} for d, a in by_day],
        "by_category": sorted(
            (
                {"category": c.value, "label": CATEGORY_LABELS[c.value], "amount_mru": int(a)}
                for c, a in by_category
            ),
            key=lambda r: -r["amount_mru"],
        ),
        "by_supplier": sorted(
            ({"supplier": k, **v} for k, v in suppliers_out.items()),
            key=lambda r: -r["amount_mru"],
        ),
        "low_stock": [
            {"id": i.id, "name": i.name, "unit": i.unit.value, "stock_qty": i.stock_qty}
            for i in session.scalars(
                select(Ingredient)
                .where(
                    Ingredient.active.is_(True),
                    Ingredient.alert_qty.is_not(None),
                    Ingredient.stock_qty <= Ingredient.alert_qty,
                )
                .order_by(Ingredient.name)
            )
        ],
    }
