"""Prévisions de ventes (J10, ADR 0015) : combien d'articles préparer aujourd'hui et les 6 jours
suivants, produit par produit.

Modèle volontairement simple, explicable à la gérante et sans dépendance lourde :
- pour un jour J, moyenne pondérée des mêmes jours de semaine des 4 dernières semaines où le
  snack a vendu (poids 4, 3, 2, 1 : la semaine la plus récente compte le plus) ;
- moins de 2 tels jours : moyenne des 14 derniers jours d'ouverture ;
- un jour sans aucune vente est un jour de fermeture : il n'entre pas dans les moyennes.

Le modèle est jugé sur le passé (« backtest ») contre la méthode naïve « comme le même jour la
semaine dernière » : l'écran dit s'il fait mieux. Sources : ventes encaissées de l'app et du
comptoir, plus l'historique Excel. Aucune donnée personnelle n'est lue.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from snacki_api.models import HistoryItem, HistorySale, OrderLine, Product
from snacki_api.pilotage import paid_orders

LOOKBACK_DAYS = 84  # 12 semaines lues
HORIZON = 7
WEIGHTS = (4, 3, 2, 1)
FALLBACK_DAYS = 14
BACKTEST_DAYS = 28
MIN_OPEN_DAYS = 14  # en dessous : prévision « insuffisante »
DAY_NAMES = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

Series = dict[date, dict[str, int]]


def load(session: Session, start: date, end: date) -> tuple[Series, set[date]]:
    """Quantités vendues par jour et par produit, et jours d'ouverture (au moins une vente)."""
    series: Series = defaultdict(lambda: defaultdict(int))
    paid = paid_orders(start, end).subquery()
    live: Sequence[Any] = session.execute(  # colonnes d'une sous-requête : non typées
        select(paid.c.service_day, OrderLine.product_id, func.sum(OrderLine.quantity))
        .join(paid, OrderLine.order_id == paid.c.id)
        .group_by(paid.c.service_day, OrderLine.product_id)
    ).all()
    old: Sequence[Any] = session.execute(
        select(HistorySale.service_day, HistoryItem.product_id, func.sum(HistoryItem.quantity))
        .join(HistorySale, HistoryItem.sale_id == HistorySale.id)
        .where(HistorySale.service_day.between(start, end), HistoryItem.product_id.is_not(None))
        .group_by(HistorySale.service_day, HistoryItem.product_id)
    ).all()
    for day, pid, qty in live:
        series[day][pid] += int(qty)
    for day, pid, qty in old:
        series[day][pid] += int(qty)
    open_days = set(series)
    open_days |= set(session.scalars(select(paid.c.service_day).distinct()))
    open_days |= set(
        session.scalars(
            select(HistorySale.service_day)
            .where(HistorySale.service_day.between(start, end))
            .distinct()
        )
    )
    return series, open_days


def predict(series: Series, open_days: set[date], target: date) -> dict[str, float]:
    """Quantités attendues le jour `target`, à partir des seuls jours antérieurs."""
    same = [target - timedelta(weeks=k) for k in range(1, 9)]
    same = [d for d in same if d in open_days][: len(WEIGHTS)]
    if len(same) >= 2:
        weights = WEIGHTS[: len(same)]
        days = list(zip(same, weights, strict=True))
    else:
        recent = sorted(d for d in open_days if d < target)[-FALLBACK_DAYS:]
        days = [(d, 1) for d in recent]
    if not days:
        return {}
    total = sum(w for _, w in days)
    out: dict[str, float] = defaultdict(float)
    for d, w in days:
        for pid, qty in series.get(d, {}).items():
            out[pid] += qty * w / total
    return dict(out)


def backtest(series: Series, open_days: set[date], today: date) -> dict:
    """Erreur moyenne (articles par jour) du modèle et de la méthode naïve sur 4 semaines."""
    model_err: list[float] = []
    naive_err: list[float] = []
    for d in sorted(x for x in open_days if today - timedelta(days=BACKTEST_DAYS) <= x < today):
        last_week = d - timedelta(weeks=1)
        if last_week not in open_days:
            continue  # la méthode naïve n'a rien à proposer : jour non comparable
        actual = sum(series.get(d, {}).values())
        model_err.append(abs(sum(predict(series, open_days, d).values()) - actual))
        naive_err.append(abs(sum(series.get(last_week, {}).values()) - actual))
    n = len(model_err)
    return {
        "days": n,
        "model_error": round(sum(model_err) / n, 1) if n else None,
        "naive_error": round(sum(naive_err) / n, 1) if n else None,
    }


def reliability(open_count: int, check: dict) -> str:
    if open_count < MIN_OPEN_DAYS:
        return "insuffisante"
    if check["days"] >= 8 and check["model_error"] <= check["naive_error"]:
        return "bonne"
    return "indicative"


def forecast(session: Session, today: date) -> dict:
    """Prévisions d'aujourd'hui à J+6, calculées sur les ventes jusqu'à hier."""
    series, open_days = load(session, today - timedelta(days=LOOKBACK_DAYS), today - timedelta(1))
    products = {p.id: p for p in session.scalars(select(Product))}
    days = []
    for k in range(HORIZON):
        target = today + timedelta(days=k)
        expected = predict(series, open_days, target)
        counts = sorted(
            ((pid, round(q)) for pid, q in expected.items() if pid in products and round(q) >= 1),
            key=lambda c: (-c[1], products[c[0]].name_fr),
        )
        items = [
            {"product_id": pid, "label": products[pid].name_fr, "quantity": q} for pid, q in counts
        ]
        days.append(
            {
                "day": target,
                "weekday": DAY_NAMES[target.weekday()],
                "units": sum(q for _, q in counts),
                "revenue_mru": sum(q * products[pid].price_mru for pid, q in counts),
                "items": items,
            }
        )
    check = backtest(series, open_days, today)
    return {
        "generated_for": today,
        "open_days": len(open_days),
        "reliability": reliability(len(open_days), check),
        "backtest": check,
        "days": days,
    }
