"""Historique Excel (J8) : lecture du classeur de suivi, reconnaissance des articles, import.

Le classeur « Suivi Dashboard » tient une feuille « Ventes » remplie à la main avant l'app :
un bloc de colonnes par jour (« J3 04/09/2026 »), puis une ligne par commande :
« cmd4 | 2 crepes + 2 jus fraises | 4 | 4400 ».

Règles :
- seule la feuille « Ventes » est lue (les autres contiennent des données d'associés) ;
- les montants sont en ancienne ouguiya (MRO) : divisés par 10 pour obtenir des MRU ;
- le texte libre est découpé sur « + » et chaque morceau rapproché d'un produit du menu ;
  ce qui n'est pas reconnu reste « hors menu », avec son montant compté dans le chiffre d'affaires ;
- l'import remplace les jours présents dans le fichier : relancer le même fichier ne double rien.

L'import est un script d'administration (ADR 0010), jamais un téléversement web (ASVS V1.5.1).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from snacki_api.models import HistoryItem, HistorySale

MAX_FILE_BYTES = 5 * 1024 * 1024
SHEET = "Ventes"
DAY_HEADER = re.compile(r"^\s*J\d+\s+(\d{2})/(\d{2})/(\d{4})\s*$")
ORDER_REF = re.compile(r"^\s*cmd\s*(\d{1,4})\s*$", re.IGNORECASE)
PART = re.compile(r"^\s*(\d{1,3})?\s*(.*?)\s*$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")

# Mot-clé (sans accent, en minuscules) → produit du menu. Le premier qui correspond gagne.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("banane-fraise", ("banane-fraise", "banane fraise")),
    ("salade", ("salade", "slade")),  # « slade » : faute de frappe vue dans le classeur
    ("crepe", ("crepe",)),
    ("avocat", ("avocat",)),
    ("mangue", ("mangue", "mango")),
    ("fraise", ("fraise",)),
    ("cocktail", ("cocktail", "cokctail")),
    ("orange", ("orange",)),
    ("mojito", ("mojito",)),
]


class HistoryError(ValueError):
    """Fichier refusé (taille, format, feuille absente)."""


@dataclass
class Item:
    product_id: str | None
    label: str
    quantity: int


@dataclass
class Sale:
    day: date
    ref: str
    raw_text: str
    total_mru: int
    items: list[Item] = field(default_factory=list)


def plain(text: str) -> str:
    """Minuscules, sans accent ni caractère de contrôle, espaces réduits."""
    text = CONTROL.sub(" ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def match_product(label: str) -> str | None:
    for product_id, words in KEYWORDS:
        if any(w in label for w in words):
            return product_id
    return None


def parse_items(text: str) -> list[Item]:
    """« 2 crepes + 2 jus fraises » → [crepe × 2, fraise × 2]."""
    items: list[Item] = []
    for part in re.sub(r"[()?]", " ", plain(text)).split("+"):
        part = part.strip()
        if not part:
            continue
        m = PART.match(part)
        qty = int(m.group(1)) if m and m.group(1) else 1
        label = (m.group(2) if m else part)[:60] or "article"
        items.append(Item(match_product(label), label, max(1, min(qty, 100))))
    return items


def _day(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        m = DAY_HEADER.match(value)
        if m:
            d, mo, y = (int(x) for x in m.groups())
            return date(y, mo, d)
    return None


def _amount(value: object, divisor: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value != value or value <= 0:  # NaN ou montant nul
        return None
    return round(value / divisor)


def sales_from_grid(grid: list[list[object]], divisor: int = 10) -> list[Sale]:
    """Parcourt la feuille : chaque en-tête de jour ouvre un bloc de 4 colonnes vers le bas."""
    headers = [
        (r, c, d)
        for r, row in enumerate(grid)
        for c, cell in enumerate(row)
        if isinstance(cell, str) and (d := _day(cell))
    ]
    sales: list[Sale] = []
    for r, c, day in headers:
        for row in grid[r + 1 :]:
            cells = (list(row) + [None] * 4)[c : c + 4]
            if isinstance(cells[0], str) and _day(cells[0]):
                break  # bloc de la semaine suivante
            ref, text, _qty, price = cells
            if not (isinstance(ref, str) and ORDER_REF.match(ref)):
                continue
            amount = _amount(price, divisor)
            if amount is None or not isinstance(text, str) or not text.strip():
                continue
            raw = CONTROL.sub(" ", text).strip()[:200]
            sales.append(Sale(day, plain(ref).replace(" ", ""), raw, amount, parse_items(raw)))
    return sales


def read_workbook(path: Path, divisor: int = 10) -> tuple[list[Sale], str]:
    """Lit la feuille « Ventes » d'un .xlsx ; renvoie les ventes et l'empreinte du fichier."""
    if path.suffix.lower() != ".xlsx":
        raise HistoryError("Fichier .xlsx attendu")
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise HistoryError("Fichier trop volumineux (5 Mo au plus)")
    # Importés ici : pandas et openpyxl ne servent qu'à ce script, pas à l'API en ligne.
    import defusedxml  # noqa: F401  (openpyxl l'utilise pour se protéger des bombes XML)
    import pandas as pd

    try:
        frame = pd.read_excel(path, sheet_name=SHEET, header=None, engine="openpyxl")
    except ValueError as exc:
        raise HistoryError(f"Feuille « {SHEET} » introuvable") from exc
    grid = frame.astype(object).where(frame.notna(), None).values.tolist()
    return sales_from_grid(grid, divisor), hashlib.sha256(data).hexdigest()[:16]


@dataclass
class Report:
    days: int
    sales: int
    total_mru: int
    unknown: Counter[str]


def import_sales(session: Session, sales: list[Sale], batch: str) -> Report:
    """Remplace l'historique des jours présents dans le fichier, en une transaction."""
    days = sorted({s.day for s in sales})
    if days:
        session.execute(delete(HistorySale).where(HistorySale.service_day.in_(days)))
    seen: set[tuple[date, str]] = set()
    kept: list[Sale] = []
    for s in sales:
        key = (s.day, s.ref)
        if key in seen:  # deux lignes « cmd3 » le même jour : on garde la première
            continue
        seen.add(key)
        kept.append(s)
        session.add(
            HistorySale(
                service_day=s.day,
                ref=s.ref,
                raw_text=s.raw_text,
                total_mru=s.total_mru,
                batch=batch,
                items=[
                    HistoryItem(product_id=i.product_id, label=i.label, quantity=i.quantity)
                    for i in s.items
                ],
            )
        )
    session.commit()
    unknown = Counter(i.label for s in kept for i in s.items if i.product_id is None)
    return Report(len(days), len(kept), sum(s.total_mru for s in kept), unknown)
