"""Commandes : création côté serveur et suivi par jeton.

Règles de sécurité (modèle de menaces) :
- T01 : le total est calculé ici, à partir des prix lus en base ; le client n'en envoie aucun.
- T02 : le jeton de suivi fait 128 bits aléatoires ; seule son empreinte SHA-256 est stockée ;
  il expire au bout de 24 h. Sans le bon jeton, aucune commande n'est lisible (anti-BOLA).
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from snacki_api.models import Order, OrderLine, Product
from snacki_api.schemas import OrderIn

TOKEN_BYTES = 16  # 128 bits (ASVS V7.2.3 : au moins 128 bits d'entropie)
TOKEN_TTL = timedelta(hours=24)


class ProduitIndisponible(ValueError):
    """Un produit demandé n'existe pas ou n'est plus disponible."""


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_order(session: Session, data: OrderIn) -> tuple[Order, str]:
    """Crée la commande et renvoie (commande, jeton de suivi en clair)."""
    ids = [item.product_id for item in data.items]
    prices = dict(
        session.execute(
            select(Product.id, Product.price_mru).where(
                Product.id.in_(ids), Product.available.is_(True)
            )
        ).all()
    )
    missing = sorted(set(ids) - prices.keys())
    if missing:
        raise ProduitIndisponible(", ".join(missing))

    now = datetime.now(UTC)
    day = now.date()  # Nouadhibou est à UTC+0, sans heure d'été
    # Numéro du jour : un verrou par jour sérialise les créations simultanées (pas de doublon).
    session.execute(select(func.pg_advisory_xact_lock(int(f"{day:%Y%m%d}"))))
    last = session.scalar(select(func.max(Order.daily_no)).where(Order.service_day == day))

    token = secrets.token_urlsafe(TOKEN_BYTES)
    order = Order(
        service_day=day,
        daily_no=(last or 0) + 1,
        customer_name=data.customer_name,
        phone=data.phone,
        fulfilment=data.fulfilment,
        landmark=data.landmark,
        tracking_hash=token_hash(token),
        tracking_expires_at=now + TOKEN_TTL,
        lines=[
            OrderLine(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price_mru=prices[item.product_id],
            )
            for item in data.items
        ],
    )
    order.total_mru = sum(line.line_total_mru for line in order.lines)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order, token


def find_by_token(session: Session, token: str) -> Order | None:
    """Commande correspondant au jeton, s'il est valide et non expiré ; sinon None."""
    if not 16 <= len(token) <= 64:
        return None
    return session.scalars(
        select(Order)
        .options(selectinload(Order.lines))
        .where(Order.tracking_hash == token_hash(token))
        .where(Order.tracking_expires_at > func.now())
    ).one_or_none()
