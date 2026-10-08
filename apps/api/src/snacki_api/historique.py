"""Historique des actions du staff (v1.1, réunion 5, demande 4).

Lecture seule du journal d'audit (T11) : qui a fait quoi et quand, filtrable par période,
par personne et par famille d'actions. Gérante et admin seulement ; l'API n'offre toujours
aucune route pour modifier ou effacer le journal.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from snacki_api.models import AuditLog, StaffUser

LIMIT = 500
LABELS: dict[str, tuple[str, str]] = {
    # action : (libellé, famille)
    "order_accepted": ("Commande acceptée", "commandes"),
    "order_status": ("Statut changé", "commandes"),
    "customer_called": ("Client appelé", "commandes"),
    "order_refused": ("Commande refusée", "refus"),
    "order_cancelled": ("Commande annulée", "refus"),
    "order_paid": ("Encaissement", "encaissements"),
    "counter_sale": ("Vente au comptoir", "encaissements"),
    "loyalty_stamp": ("Tampon fidélité", "fidelite"),
    "loyalty_reward": ("Cadeau fidélité", "fidelite"),
    "loyalty_revoke": ("Tampon retiré", "fidelite"),
    "loyalty_restore": ("Cadeau rendu", "fidelite"),
    "loyalty_transfer": ("Tampons reportés", "fidelite"),
    "loyalty_block": ("Carte bloquée", "fidelite"),
    "assistant": ("Assistant IA", "ia"),
    "resume_ia": ("Résumé IA", "ia"),
    "login": ("Connexion", "connexions"),
    "logout": ("Déconnexion", "connexions"),
    "login_refused": ("Connexion refusée", "refus"),
    "access_denied": ("Accès refusé", "refus"),
    "staff_added": ("Membre ajouté", "equipe"),
    "staff_updated": ("Membre modifié", "equipe"),
    "report": ("Rapport téléchargé", "equipe"),
}
GROUPS = {
    "commandes": "Commandes",
    "encaissements": "Encaissements",
    "refus": "Refus et annulations",
    "fidelite": "Fidélité",
    "equipe": "Équipe",
    "connexions": "Connexions",
    "ia": "Intelligence artificielle",
}


VALUES = {
    "recue": "reçue", "acceptee": "acceptée", "en_preparation": "en préparation",
    "prete": "prête", "livree": "remise", "refusee": "refusée", "annulee": "annulée",
    "cash": "espèces", "bankily": "Bankily", "sedad": "Sedad", "bimbank": "Bimbank",
    "bamis": "Bamis", "delai_min": "délai (min)", "frais": "frais (MRU)",
    "montant": "montant (MRU)",
}  # fmt: skip


def _detail(detail: dict | None) -> str:
    """Résumé lisible du détail (déjà sans donnée de client : voir staff.audit)."""
    if not detail:
        return ""
    parts = []
    for key, value in detail.items():
        if value is None or isinstance(value, (dict, list)):
            continue
        parts.append(f"{VALUES.get(key, key)} : {VALUES.get(str(value), value)}")
    return " · ".join(parts)[:160]


def entries(
    session: Session,
    start: date,
    end: date,
    actor_id: int | None = None,
    group: str | None = None,
) -> dict:
    begin = datetime.combine(start, time.min, tzinfo=UTC)
    stop = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
    query = (
        select(AuditLog, StaffUser)
        .outerjoin(StaffUser, AuditLog.actor_id == StaffUser.id)
        .where(AuditLog.at >= begin, AuditLog.at < stop)
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
        .limit(LIMIT + 1)
    )
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    if group:
        actions = [a for a, (_, g) in LABELS.items() if g == group]
        query = query.where(AuditLog.action.in_(actions))
    rows = session.execute(query).all()
    out = []
    for log, user in rows[:LIMIT]:
        label, fam = LABELS.get(log.action, (log.action, "autre"))
        out.append(
            {
                "at": log.at,
                "actor": (user.display_name or user.email) if user else "Système",
                "action": log.action,
                "label": label,
                "group": fam,
                "target": log.target,
                "detail": _detail(log.detail),
            }
        )
    people = [
        {"id": u.id, "name": u.display_name or u.email}
        for u in session.scalars(select(StaffUser).order_by(StaffUser.email))
    ]
    return {"entries": out, "people": people, "groups": GROUPS, "truncated": len(rows) > LIMIT}
