"""Tâches d'exploitation.

    python -m snacki_api.manage migrate                 # job de chaque déploiement (J6, J8)
    python -m snacki_api.manage purge                   # conservation des données (J8)
    python -m snacki_api.manage import-history FICHIER.xlsx [--dry-run] [--divisor 10]
    python -m snacki_api.manage loyalty-cards --count 44 --base-url https://… --out cartes.pdf
    python -m snacki_api.manage loyalty-cards --reprint LOT --base-url https://… --out cartes.pdf

migrate :
1. applique les migrations Alembic (`upgrade head`) ;
2. crée le premier administrateur (SNACKI_BOOTSTRAP_ADMIN_EMAIL) s'il n'existe encore aucun admin ;
3. applique la politique de conservation (coordonnées des clients après 90 jours, journal 1 an).

import-history (ADR 0010) : lit la feuille « Ventes » du classeur de suivi et remplace
l'historique des jours qu'il contient. --dry-run affiche le rapport sans rien écrire.

loyalty-cards (ADR 0011) : crée des cartes de fidélité neuves (un lot) et les écrit dans un PDF
prêt à imprimer (--layout cartes : 2 cartes par A4 ; cartes4 : 4 par A4 ; etiquettes : planches) ;
--reprint réimprime un lot existant.
"""

import argparse
import hashlib
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from snacki_api import history, loyalty, loyalty_print, retention, staff
from snacki_api.config import get_settings
from snacki_api.db import get_sessionmaker
from snacki_api.models import LoyaltyCard

API_DIR = Path(__file__).resolve().parents[2]


def migrate() -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    command.upgrade(cfg, "head")
    email = get_settings().bootstrap_admin_email
    with get_sessionmaker()() as session:
        created = staff.ensure_bootstrap_admin(session, email)
        session.commit()
    print("Migrations appliquées." + (" Premier administrateur créé." if created else ""))
    purge()


def purge() -> None:
    days = get_settings().retention_days
    with get_sessionmaker()() as session:
        orders, audit = retention.purge(session, days)
    print(
        f"Conservation : {orders} commande(s) anonymisée(s), {audit} ligne(s) d'audit effacée(s)."
    )


def import_history(path: Path, divisor: int, dry_run: bool) -> None:
    sales, batch = history.read_workbook(path, divisor)
    if not sales:
        raise history.HistoryError("Aucune vente reconnue dans la feuille « Ventes »")
    days = sorted({s.day for s in sales})
    print(f"Fichier {batch} : {len(sales)} ventes, {len(days)} jours ({days[0]} → {days[-1]}).")
    print(f"Total : {sum(s.total_mru for s in sales)} MRU (montants divisés par {divisor}).")
    unknown = history.Counter(i.label for s in sales for i in s.items if i.product_id is None)
    if unknown:
        print("Hors menu (montant compté, produit non attribué) :")
        for label, n in unknown.most_common():
            print(f"  {n:3d} × {label}")
    if dry_run:
        print("Essai à blanc : rien n'a été écrit.")
        return
    with get_sessionmaker()() as session:
        report = history.import_sales(session, sales, batch)
    print(f"Importé : {report.sales} ventes sur {report.days} jours.")


def loyalty_cards(
    count: int, reprint: str | None, base_url: str, out: Path, layout: str = "cartes"
) -> None:
    if out.suffix.lower() != ".pdf":
        raise history.HistoryError("Fichier .pdf attendu pour les étiquettes")
    with get_sessionmaker()() as session:
        if reprint:
            codes = list(
                session.scalars(
                    select(LoyaltyCard.code)
                    .where(LoyaltyCard.batch == reprint)
                    .order_by(LoyaltyCard.id)
                )
            )
            if not codes:
                raise history.HistoryError(f"Lot {reprint} introuvable")
            batch = reprint
        else:
            now = datetime.now(UTC).isoformat()
            batch = "L" + hashlib.sha256(now.encode()).hexdigest()[:9].upper()
            codes = loyalty.issue(session, count, batch)
    try:
        if layout == "etiquettes":
            pages = loyalty_print.write_labels(codes, base_url, out)
        else:
            per_page = 4 if layout == "cartes4" else 2
            pages = loyalty_print.write_cards(codes, base_url, out, per_page=per_page)
    except ValueError as exc:
        raise history.HistoryError(str(exc)) from None
    print(f"Lot {batch} : {len(codes)} cartes, {pages} page(s) A4 ({layout}) dans {out}.")
    print("Imprimez, puis supprimez ce fichier : il contient des numéros valides.")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="python -m snacki_api.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("purge")
    imp = sub.add_parser("import-history")
    imp.add_argument("file", type=Path)
    imp.add_argument("--divisor", type=int, default=10, choices=(1, 10))
    imp.add_argument("--dry-run", action="store_true")
    cards = sub.add_parser("loyalty-cards")
    cards.add_argument("--count", type=int, default=44, choices=range(1, 1001), metavar="1-1000")
    cards.add_argument("--reprint", default=None)
    cards.add_argument("--base-url", required=True)
    cards.add_argument("--out", type=Path, required=True)
    cards.add_argument("--layout", choices=("cartes", "cartes4", "etiquettes"), default="cartes")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0) or 2
    try:
        if args.cmd == "migrate":
            migrate()
        elif args.cmd == "purge":
            purge()
        elif args.cmd == "loyalty-cards":
            loyalty_cards(args.count, args.reprint, args.base_url, args.out, args.layout)
        else:
            import_history(args.file, args.divisor, args.dry_run)
    except (history.HistoryError, FileNotFoundError) as exc:
        print(f"Refusé : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
