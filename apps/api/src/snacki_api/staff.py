"""Comptes du staff et journal d'audit (J6)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from snacki_api.models import AuditLog, StaffRole, StaffUser

log = logging.getLogger("snacki.staff")


class StaffError(Exception):
    """Opération refusée sur un compte du staff (message affichable)."""


def audit(
    session: Session,
    action: str,
    actor: StaffUser | None = None,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Ajoute une ligne au journal. La ligne est validée avec l'action qu'elle décrit."""
    session.add(
        AuditLog(action=action, actor_id=actor.id if actor else None, target=target, detail=detail)
    )


def by_email(session: Session, email: str) -> StaffUser | None:
    return session.scalar(select(StaffUser).where(StaffUser.email == email.strip().lower()))


def list_staff(session: Session) -> list[StaffUser]:
    return list(session.scalars(select(StaffUser).order_by(StaffUser.role, StaffUser.email)))


def _active_admins(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(StaffUser)
            .where(StaffUser.role == StaffRole.ADMIN, StaffUser.active.is_(True))
        )
        or 0
    )


def add(session: Session, actor: StaffUser | None, email: str, role: StaffRole) -> StaffUser:
    email = email.strip().lower()
    if by_email(session, email):
        raise StaffError("Cette adresse fait déjà partie de l'équipe")
    user = StaffUser(email=email, role=role)
    session.add(user)
    session.flush()
    audit(session, "staff_added", actor, email, {"role": role.value})
    return user


def update(
    session: Session,
    actor: StaffUser,
    user: StaffUser,
    role: StaffRole | None,
    active: bool | None,
) -> StaffUser:
    before = {"role": user.role.value, "active": user.active}
    if user.id == actor.id and (role not in (None, StaffRole.ADMIN) or active is False):
        # Personne ne peut se retirer ses propres droits d'admin : pas de verrouillage par erreur.
        raise StaffError("Vous ne pouvez pas retirer vos propres droits d'administration")
    if role is not None:
        user.role = role
    if active is not None:
        user.active = active
    if user.role != StaffRole.ADMIN or not user.active:
        session.flush()
        if _active_admins(session) == 0:
            raise StaffError("Il doit rester au moins un administrateur actif")
    after = {"role": user.role.value, "active": user.active}
    if after != before:
        # Toute session ouverte de ce compte devient invalide immédiatement (T12).
        user.session_version += 1
        audit(session, "staff_updated", actor, user.email, {"avant": before, "après": after})
    return user


def record_login(session: Session, user: StaffUser, name: str | None) -> None:
    user.last_login_at = datetime.now(UTC)
    if name and not user.display_name:
        user.display_name = name
    audit(session, "login", user)


def logout(session: Session, user: StaffUser) -> None:
    user.session_version += 1
    audit(session, "logout", user)


def ensure_bootstrap_admin(session: Session, email: str) -> bool:
    """Crée le premier admin s'il n'existe encore aucun admin. Renvoie True si créé."""
    email = email.strip().lower()
    if not email or _active_admins(session) > 0:
        return False
    user = by_email(session, email)
    if user is None:
        add(session, None, email, StaffRole.ADMIN)
    else:
        user.role, user.active = StaffRole.ADMIN, True
        user.session_version += 1
        audit(session, "staff_updated", None, email, {"après": {"role": "admin", "active": True}})
    log.info("Premier administrateur créé")
    return True
