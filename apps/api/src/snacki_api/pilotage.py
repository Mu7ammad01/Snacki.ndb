"""Pilotage (J8) : chiffre d'affaires, produits les plus vendus, moyens de paiement.

Deux sources, additionnées jour par jour :
- les ventes de l'app et du comptoir : commandes encaissées, ni refusées ni annulées ;
- l'historique Excel d'avant l'app (table history_sale).

Tout est calculé par PostgreSQL avec des requêtes SQLAlchemy paramétrées (aucun SQL assemblé
à partir d'une saisie). Réservé à la gérante et à l'admin (T26).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from snacki_api.models import (
    HistoryItem,
    HistorySale,
    LoyaltyCard,
    LoyaltyEvent,
    LoyaltyKind,
    Order,
    OrderLine,
    OrderSource,
    OrderStatus,
    Product,
)

MAX_DAYS = 366
TOP = 8


def paid_orders(start: date, end: date) -> Select:
    """Filtre commun : commandes encaissées, non refusées ni annulées, dans la période."""
    return select(Order).where(
        Order.paid_at.is_not(None),
        Order.status.not_in([OrderStatus.REFUSEE, OrderStatus.ANNULEE]),
        Order.service_day.between(start, end),
    )


def _live(session: Session, start: date, end: date):
    paid = paid_orders(start, end).subquery()
    return session.execute(
        select(
            paid.c.service_day,
            paid.c.source,
            func.count(),
            func.sum(paid.c.total_mru + paid.c.delivery_fee_mru - paid.c.discount_mru),
        ).group_by(paid.c.service_day, paid.c.source)
    ).all()


def _history(session: Session, start: date, end: date):
    return session.execute(
        select(HistorySale.service_day, func.count(), func.sum(HistorySale.total_mru))
        .where(HistorySale.service_day.between(start, end))
        .group_by(HistorySale.service_day)
    ).all()


def _top(session: Session, start: date, end: date) -> list[dict]:
    paid = paid_orders(start, end).subquery()
    live = session.execute(
        select(
            OrderLine.product_id,
            func.sum(OrderLine.quantity),
            func.sum(OrderLine.quantity * OrderLine.unit_price_mru),
        )
        .join(paid, OrderLine.order_id == paid.c.id)
        .group_by(OrderLine.product_id)
    ).all()
    old = session.execute(
        select(HistoryItem.product_id, func.sum(HistoryItem.quantity))
        .join(HistorySale, HistoryItem.sale_id == HistorySale.id)
        .where(HistorySale.service_day.between(start, end))
        .group_by(HistoryItem.product_id)
    ).all()
    names = dict(session.execute(select(Product.id, Product.name_fr)).all())
    qty: dict[str | None, int] = defaultdict(int)
    revenue: dict[str | None, int] = defaultdict(int)
    for pid, q, r in live:
        qty[pid] += int(q)
        revenue[pid] += int(r)
    for old_pid, q in old:
        qty[old_pid] += int(q)
    rows: list[dict[str, Any]] = [
        {
            "product_id": pid,
            "label": names.get(pid, "Hors menu") if pid else "Hors menu",
            "quantity": q,
            "revenue_mru": revenue.get(pid, 0),
        }
        for pid, q in qty.items()
    ]
    return sorted(rows, key=lambda r: (-r["quantity"], r["label"]))[:TOP]


def _payments(session: Session, start: date, end: date) -> list[dict]:
    paid = paid_orders(start, end).subquery()
    rows: Sequence[Any] = session.execute(  # colonnes d'une sous-requête : non typées
        select(
            paid.c.paid_method,
            func.count(),
            func.sum(paid.c.total_mru + paid.c.delivery_fee_mru - paid.c.discount_mru),
        ).group_by(paid.c.paid_method)
    ).all()
    return sorted(
        ({"method": m.value, "count": int(n), "amount_mru": int(a)} for m, n, a in rows),
        key=lambda r: -r["amount_mru"],
    )


def _loyalty(session: Session, start: date, end: date) -> dict:
    paid = paid_orders(start, end).subquery()
    rewards, discount = session.execute(
        select(func.count(), func.coalesce(func.sum(paid.c.discount_mru), 0)).where(
            paid.c.discount_mru > 0
        )
    ).one()
    stamps = session.scalar(
        select(func.count())
        .select_from(LoyaltyEvent)
        .where(
            LoyaltyEvent.kind == LoyaltyKind.STAMP,
            func.date(LoyaltyEvent.at).between(start, end),
        )
    )
    active = session.scalar(
        select(func.count()).select_from(LoyaltyCard).where(LoyaltyCard.last_stamp_at.is_not(None))
    )
    return {
        "stamps": int(stamps or 0),
        "rewards": int(cast(int, rewards)),
        "discount_mru": int(cast(int, discount)),
        "active_cards": int(active or 0),
    }


def all_time(session: Session) -> int:
    paid = paid_orders(date(2000, 1, 1), date(2999, 12, 31)).subquery()
    live = (
        session.scalar(
            select(func.sum(paid.c.total_mru + paid.c.delivery_fee_mru - paid.c.discount_mru))
        )
        or 0
    )
    old = session.scalar(select(func.sum(HistorySale.total_mru))) or 0
    return int(live) + int(old)


def summary(session: Session, start: date, end: date) -> dict:
    by_day: dict[date, dict] = {}

    def day(d: date) -> dict:
        return by_day.setdefault(
            d, {"day": d, "app_mru": 0, "comptoir_mru": 0, "historique_mru": 0}
        )

    orders = 0
    for d, source, n, amount in _live(session, start, end):
        key = "app_mru" if source == OrderSource.APP else "comptoir_mru"
        day(d)[key] += int(amount)
        orders += int(n)
    for d, n, amount in _history(session, start, end):
        day(d)["historique_mru"] += int(amount)
        orders += int(n)

    points = [by_day[d] for d in sorted(by_day)]
    revenue = sum(p["app_mru"] + p["comptoir_mru"] + p["historique_mru"] for p in points)
    today = datetime.now(UTC).date()  # Nouadhibou vit à UTC+0
    today_mru = sum(int(a) for *_, a in _live(session, today, today)) + sum(
        int(a) for *_, a in _history(session, today, today)
    )
    span = select(func.min(HistorySale.service_day), func.max(HistorySale.service_day))
    first, last = session.execute(span).one()
    return {
        "start": start,
        "end": end,
        "revenue_mru": revenue,
        "orders": orders,
        "average_basket_mru": round(revenue / orders) if orders else 0,
        "today_mru": today_mru,
        "all_time_mru": all_time(session),
        "by_day": points,
        "top": _top(session, start, end),
        "payments": _payments(session, start, end),
        "history_first": first,
        "history_last": last,
        "loyalty": _loyalty(session, start, end),
    }


def default_period() -> tuple[date, date]:
    end = datetime.now(UTC).date()
    return end - timedelta(days=29), end
