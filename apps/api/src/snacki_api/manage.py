"""Tâches d'exploitation.

    python -m snacki_api.manage migrate                 # job de chaque déploiement (J6, J8)
    python -m snacki_api.manage purge                   # conservation des données (J8)
    python -m snacki_api.manage import-history FICHIER.xlsx [--dry-run] [--divisor 10]

migrate :
1. applique les migrations Alembic (`upgrade head`) ;
2. crée le premier administrateur (SNACKI_BOOTSTRAP_ADMIN_EMAIL) s'il n'existe encore aucun admin ;
3. applique la politique de conservation (coordonnées des clients après 90 jours, journal 1 an).

import-history (ADR 0010) : lit la feuille « Ventes » du classeur de suivi et remplace
l'historique des jours qu'il contient. --dry-run affiche le rapport sans rien écrire.
"""

import argparse
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from snacki_api import history, retention, staff
from snacki_api.config import get_settings
from snacki_api.db import get_sessionmaker

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
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0) or 2
    try:
        if args.cmd == "migrate":
            migrate()
        elif args.cmd == "purge":
            purge()
        else:
            import_history(args.file, args.divisor, args.dry_run)
    except history.HistoryError as exc:
        print(f"Refusé : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
