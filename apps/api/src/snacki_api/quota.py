"""Plafond quotidien d'appels à l'IA (J10, menace T15 : épuisement du quota Gemini).

Le compteur est dans PostgreSQL : il vaut pour toutes les instances Cloud Run à la fois. Une
seule requête atomique incrémente le compteur seulement s'il est sous le plafond ; au-delà,
l'app bascule sur ses méthodes sans IA (analyse locale, résumé modèle) et le dit.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from snacki_api.models import AiUsage


def take(session: Session, feature: str, cap: int, day: date) -> bool:
    """Réserve un appel. True si accordé ; à valider (commit) avec le reste de la requête."""
    if cap <= 0:
        return False
    stmt = (
        insert(AiUsage)
        .values(day=day, feature=feature, calls=1)
        .on_conflict_do_update(
            index_elements=[AiUsage.day, AiUsage.feature],
            set_={"calls": AiUsage.calls + 1},
            where=AiUsage.calls < cap,
        )
        .returning(AiUsage.calls)
    )
    return session.execute(stmt).first() is not None


def used(session: Session, feature: str, day: date) -> int:
    row = session.get(AiUsage, (day, feature))
    return row.calls if row else 0
