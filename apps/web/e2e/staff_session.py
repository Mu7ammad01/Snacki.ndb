"""Tests de bout en bout (J11) : crée un compte du staff dans la base JETABLE de la CI et affiche
un jeton de session, posé ensuite dans le cookie du navigateur de test.

Aucune porte dérobée dans l'app : le jeton est signé avec la clé de session de la CI, comme
après une vraie connexion Google. Refuse de tourner hors environnement « test ».

    python e2e/staff_session.py <caissier|gerante|admin>
"""

import sys

from snacki_api import auth
from snacki_api.config import get_settings
from snacki_api.db import get_sessionmaker
from snacki_api.models import StaffRole, StaffUser

settings = get_settings()
if settings.environment != "test":
    sys.exit("Réservé à la base jetable des tests (SNACKI_ENVIRONMENT=test)")
role = StaffRole(sys.argv[1])
secret = settings.session_secret.get_secret_value() if settings.session_secret else ""
with get_sessionmaker()() as s:
    email = f"e2e-{role.value}@example.com"
    user = s.query(StaffUser).filter_by(email=email).one_or_none()
    if user is None:
        user = StaffUser(email=email, role=role, display_name=f"E2E {role.value}")
        s.add(user)
        s.commit()
    print(auth.new_session(secret, user.id, user.session_version, 1))
