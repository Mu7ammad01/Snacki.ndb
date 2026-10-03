"""Tâches d'exploitation, lancées par le Cloud Run Job de chaque déploiement (J6).

    python -m snacki_api.manage migrate

1. applique les migrations Alembic (`upgrade head`) ;
2. crée le premier administrateur (SNACKI_BOOTSTRAP_ADMIN_EMAIL) s'il n'existe encore aucun admin.
   Les autres membres sont ajoutés ensuite par l'admin, depuis l'écran « Équipe ».
"""

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from snacki_api import staff
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


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    if argv == ["migrate"]:
        migrate()
        return 0
    print("Usage : python -m snacki_api.manage migrate", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
