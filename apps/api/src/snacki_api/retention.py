"""Conservation des données (J8), selon l'inventaire du modèle de menaces :

- coordonnées des clients (prénom, téléphone, repère, remarque) : effacées 90 jours après la
  commande ; les montants, produits et dates restent pour le pilotage ;
- journal d'audit : 1 an.

Lancé à chaque déploiement par le job de migration (`python -m snacki_api.manage migrate`)
et à la demande (`python -m snacki_api.manage purge`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, update
from sqlalchemy.orm import Session

from snacki_api.models import AuditLog, Order, OrderStatus

AUDIT_DAYS = 365
CLOSED = (OrderStatus.LIVREE, OrderStatus.REFUSEE, OrderStatus.ANNULEE)


def purge(session: Session, retention_days: int, now: datetime | None = None) -> tuple[int, int]:
    """Anonymise les commandes closes trop anciennes et supprime le vieux journal."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=retention_days)
    orders = session.execute(
        update(Order)
        .where(
            Order.created_at < cutoff,
            Order.anonymized_at.is_(None),
            Order.status.in_(CLOSED),
        )
        .values(
            customer_name="Client",
            phone=None,
            # une livraison garde un repère (contrainte de la base), mais plus le vrai
            landmark=case((Order.landmark.is_(None), None), else_="—"),
            note=None,
            anonymized_at=now,
        )
    ).rowcount
    audit = session.execute(
        delete(AuditLog).where(AuditLog.at < now - timedelta(days=AUDIT_DAYS))
    ).rowcount
    session.commit()
    return orders, audit
