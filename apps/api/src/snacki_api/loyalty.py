"""Fidélité (J8 bis) : 5 commandes encaissées = 1 commande offerte, jusqu'à 100 MRU.

Une carte porte un numéro unique imprimé en clair et dans un QR : « FID-7KQ2-M9XA ».
Les tampons n'existent que dans la base ; rien n'est tamponné sur le papier.

Mesures anti-fraude (T28, ADR 0011) :
- numéro aléatoire (7 caractères, 34 milliards de possibilités) + caractère de contrôle
  (Luhn mod 32) : une faute de frappe est refusée tout de suite, un numéro deviné presque jamais
  valide ; seules les cartes émises par Snacki existent en base ;
- un tampon = une commande encaissée, donnée par le staff (contrainte d'unicité en base) ;
- au plus 3 tampons par carte et par jour, 10 minutes au moins entre deux tampons ;
- la commande offerte ne donne pas de tampon ; annuler une commande retire son tampon
  ou rend les tampons du cadeau ;
- carte verrouillée pendant l'action (deux caisses, un seul cadeau) ;
- carte perdue : la gérante la bloque et reporte les tampons sur une nouvelle ;
- chaque mouvement est inscrit dans le grand livre (loyalty_event) et le journal d'audit.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from snacki_api import staff
from snacki_api.models import (
    CardStatus,
    LoyaltyCard,
    LoyaltyEvent,
    LoyaltyKind,
    Order,
    OrderStatus,
    StaffRole,
    StaffUser,
)

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # base 32 de Crockford : ni I, L, O, U
GOAL = 5
REWARD_MAX_MRU = 100
MAX_STAMPS_PER_DAY = 3
MIN_GAP = timedelta(minutes=10)
MANAGERS = (StaffRole.GERANTE, StaffRole.ADMIN)
CODE_IN_TEXT = re.compile(r"FID[-\s]*([0-9A-Z]{4})[-\s]*([0-9A-Z]{4})", re.IGNORECASE)


class LoyaltyError(Exception):
    """Action refusée sur la carte (409), ou carte inconnue."""


def _check_char(body: str) -> str:
    """Luhn mod 32 : détecte toute erreur sur un caractère et presque toute inversion."""
    n = len(ALPHABET)
    total, factor = 0, 2
    for ch in reversed(body):
        addend = factor * ALPHABET.index(ch)
        total += addend // n + addend % n
        factor = 1 if factor == 2 else 2
    return ALPHABET[(n - total % n) % n]


def new_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(7))
    return body + _check_char(body)


def display(code: str) -> str:
    return f"FID-{code[:4]}-{code[4:]}"


def normalize(text: str) -> str | None:
    """Numéro saisi ou lu dans le QR (lien …/carte#FID-…) → 8 caractères valides, sinon None."""
    if not isinstance(text, str) or len(text) > 200:
        return None
    raw = text.upper()
    m = CODE_IN_TEXT.search(raw)
    code = m.group(1) + m.group(2) if m else re.sub(r"[\s-]", "", raw)
    code = code.replace("O", "0").replace("I", "1").replace("L", "1")  # confusions courantes
    if not re.fullmatch(rf"[{ALPHABET}]{{8}}", code):
        return None
    return code if _check_char(code[:7]) == code[7] else None


def find(session: Session, text: str, lock: bool = False) -> LoyaltyCard:
    code = normalize(text)
    if code is None:
        raise LoyaltyError("Numéro de carte invalide")
    query = select(LoyaltyCard).where(LoyaltyCard.code == code)
    if lock:
        query = query.with_for_update()
    card = session.scalars(query).one_or_none()
    if card is None:
        raise LoyaltyError("Carte inconnue")
    return card


def summary(card: LoyaltyCard) -> dict:
    return {
        "card": display(card.code),
        "status": card.status.value,
        "stamps": card.stamps,
        "progress": card.stamps % GOAL,
        "goal": GOAL,
        "rewards_available": card.stamps // GOAL,
        "rewards_taken": card.rewards,
        "phone_linked": card.phone is not None,
    }


def _event(session, card, kind, delta, order=None, actor=None):
    session.add(
        LoyaltyEvent(
            card_id=card.id,
            kind=kind,
            delta=delta,
            order_id=order.id if order else None,
            actor_id=actor.id if actor else None,
        )
    )
    staff.audit(
        session,
        f"loyalty_{kind.value}",
        actor,
        display(card.code),
        {"commande": order.number if order else None, "tampons": card.stamps},
    )


def _usable(card: LoyaltyCard) -> None:
    if card.status is CardStatus.BLOCKED:
        raise LoyaltyError("Carte bloquée : voir la gérante")


def stamp(
    session: Session, actor: StaffUser, order: Order, text: str, phone: str | None = None
) -> LoyaltyCard:
    """Tampon pour une commande encaissée (une seule fois par commande)."""
    if order.paid_at is None or order.status in {OrderStatus.REFUSEE, OrderStatus.ANNULEE}:
        raise LoyaltyError("Le tampon se donne après l'encaissement")
    if order.loyalty_card_id is not None:
        raise LoyaltyError("Cette commande est déjà liée à une carte")
    if order.discount_mru:
        raise LoyaltyError("La commande offerte ne donne pas de tampon")
    card = find(session, text, lock=True)
    _usable(card)
    now = datetime.now(UTC)
    if card.last_stamp_at and now - card.last_stamp_at < MIN_GAP:
        raise LoyaltyError("Un tampon a déjà été donné il y a moins de 10 minutes")
    today = session.scalar(
        select(func.count())
        .select_from(LoyaltyEvent)
        .where(
            LoyaltyEvent.card_id == card.id,
            LoyaltyEvent.kind == LoyaltyKind.STAMP,
            LoyaltyEvent.at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
    )
    if today >= MAX_STAMPS_PER_DAY:
        raise LoyaltyError("3 tampons au plus par carte et par jour")
    if phone and card.phone is None:
        card.phone = phone
    card.status = CardStatus.ACTIVE
    card.stamps += 1
    card.last_stamp_at = now
    order.loyalty_card_id = card.id
    _event(session, card, LoyaltyKind.STAMP, 1, order, actor)
    return card


def redeem(session: Session, actor: StaffUser, order: Order, text: str) -> LoyaltyCard:
    """Cadeau : 100 MRU au plus retirés d'une commande pas encore encaissée."""
    if order.paid_at is not None:
        raise LoyaltyError("Le cadeau s'applique avant l'encaissement")
    if order.status not in {OrderStatus.ACCEPTEE, OrderStatus.EN_PREPARATION, OrderStatus.PRETE}:
        raise LoyaltyError("Acceptez d'abord la commande")
    if order.discount_mru or order.loyalty_card_id is not None:
        raise LoyaltyError("Cette commande est déjà liée à une carte")
    card = find(session, text, lock=True)
    _usable(card)
    if card.stamps < GOAL:
        raise LoyaltyError(f"Pas encore de cadeau : {card.stamps} tampon(s) sur {GOAL}")
    card.stamps -= GOAL
    card.rewards += 1
    order.discount_mru = min(REWARD_MAX_MRU, order.total_mru)
    order.loyalty_card_id = card.id
    _event(session, card, LoyaltyKind.REWARD, -GOAL, order, actor)
    return card


def on_cancel(session: Session, actor: StaffUser, order: Order) -> None:
    """Commande annulée : on retire son tampon, ou on rend les tampons de son cadeau."""
    if order.loyalty_card_id is None:
        return
    card = session.scalars(
        select(LoyaltyCard).where(LoyaltyCard.id == order.loyalty_card_id).with_for_update()
    ).one()
    if order.discount_mru:
        card.stamps += GOAL
        card.rewards = max(0, card.rewards - 1)
        _event(session, card, LoyaltyKind.RESTORE, GOAL, order, actor)
    else:
        card.stamps = max(0, card.stamps - 1)
        _event(session, card, LoyaltyKind.REVOKE, -1, order, actor)


def block(session: Session, actor: StaffUser, text: str, reason: str) -> LoyaltyCard:
    if actor.role not in MANAGERS:  # défense en profondeur : la route l'exige déjà
        raise PermissionError
    card = find(session, text, lock=True)
    card.status = CardStatus.BLOCKED
    card.blocked_reason = reason
    staff.audit(session, "loyalty_block", actor, display(card.code), {"motif": reason})
    return card


def transfer(session: Session, actor: StaffUser, old_text: str, new_text: str) -> LoyaltyCard:
    """Carte perdue : tampons reportés sur une carte neuve, l'ancienne est bloquée."""
    if actor.role not in MANAGERS:
        raise PermissionError
    old = find(session, old_text, lock=True)
    new = find(session, new_text, lock=True)
    if old.id == new.id:
        raise LoyaltyError("Choisissez une autre carte")
    if new.status is not CardStatus.ISSUED:
        raise LoyaltyError("La nouvelle carte doit être neuve")
    moved = old.stamps
    new.stamps, new.phone, new.status = moved, old.phone, CardStatus.ACTIVE
    old.stamps, old.status = 0, CardStatus.BLOCKED
    old.blocked_reason = f"Remplacée par {display(new.code)}"
    _event(session, new, LoyaltyKind.TRANSFER, moved, None, actor)
    _event(session, old, LoyaltyKind.TRANSFER, -moved, None, actor)
    return new


def search_phone(session: Session, phone: str) -> list[LoyaltyCard]:
    return list(
        session.scalars(
            select(LoyaltyCard).where(LoyaltyCard.phone == phone).order_by(LoyaltyCard.id)
        )
    )


def issue(session: Session, count: int, batch: str) -> list[str]:
    """Crée des cartes neuves ; renvoie leurs numéros pour l'impression des étiquettes."""
    existing = set(session.scalars(select(LoyaltyCard.code)))
    codes: list[str] = []
    while len(codes) < count:
        code = new_code()
        if code not in existing:
            existing.add(code)
            codes.append(code)
            session.add(LoyaltyCard(code=code, status=CardStatus.ISSUED, batch=batch))
    session.commit()
    return codes
