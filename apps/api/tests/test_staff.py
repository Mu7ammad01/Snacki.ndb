"""J6 : connexion du staff (OAuth Google + PKCE), sessions, rôles et journal d'audit.

Google est simulé : une vraie paire de clés RSA signe des jetons d'identité de test, et le
point d'échange du code est remplacé par un transport httpx local. Le code de vérification
de l'API, lui, est le vrai.
"""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text

from snacki_api import auth, staff
from snacki_api.config import Settings
from snacki_api.db import get_sessionmaker
from snacki_api.main import create_app
from snacki_api.models import AuditLog, StaffRole, StaffUser

CLIENT_ID = "client-test.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_ROUTES = {
    "/healthz",
    "/readyz",
    "/v1/menu",
    "/v1/menu/{product_id}",
    "/v1/orders",
    "/v1/orders/track",
    "/v1/auth/start",
    "/v1/auth/callback",
}


class FakeGoogle:
    """Ce que Google renverrait. `claims` permet de fabriquer de mauvais jetons."""

    def __init__(self) -> None:
        self.claims: dict = {}
        self.key = GOOGLE_KEY
        self.algorithm = "RS256"
        self.last_verifier: str | None = None
        self.challenge: str | None = None

    def id_token(self, nonce: str) -> str:
        now = datetime.now(UTC)
        claims = {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "sub": "1234567890",
            "email": self.email,
            "email_verified": True,
            "name": "Aïcha",
            "nonce": nonce,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            **self.claims,
        }
        return jwt.encode(claims, self.key, algorithm=self.algorithm)

    def transport(self, request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        self.last_verifier = form["code_verifier"][0]
        return httpx.Response(200, json={"id_token": self.id_token(self.nonce)})


@pytest.fixture(autouse=True)
def equipe_vide():
    with get_sessionmaker()() as s:
        s.execute(text("TRUNCATE audit_log, staff_user RESTART IDENTITY CASCADE"))
        s.commit()


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


@pytest.fixture
def auth_settings(settings) -> Settings:
    return settings.model_copy(
        update={
            "oauth_client_id": CLIENT_ID,
            "oauth_client_secret": SecretStr("secret-de-test"),
            "oauth_redirect_uri": "https://web.test/auth/callback",
            "session_secret": SecretStr("k" * 48),
        }
    )


@pytest.fixture
def api(auth_settings, google) -> TestClient:
    oidc = auth.GoogleOIDC(
        CLIENT_ID,
        "secret-de-test",
        "https://web.test/auth/callback",
        http=httpx.Client(transport=httpx.MockTransport(google.transport)),
        signing_key=lambda _token: GOOGLE_KEY.public_key(),
    )
    return TestClient(create_app(auth_settings, oidc))


def membre(email: str, role: StaffRole, active: bool = True) -> int:
    with get_sessionmaker()() as s:
        user = StaffUser(email=email, role=role, active=active)
        s.add(user)
        s.commit()
        return user.id


def connexion(api: TestClient, google: FakeGoogle, email: str, **tamper) -> httpx.Response:
    """Parcours complet : start, retour de Google, callback. `tamper` modifie une étape."""
    start = api.post("/v1/auth/start").json()
    query = parse_qs(urlsplit(start["authorization_url"]).query)
    google.email = email
    google.nonce = tamper.pop("nonce", query["nonce"][0])
    google.challenge = query["code_challenge"][0]
    body = {"code": "4/code-de-test-google", "state": query["state"][0], "flow": start["flow"]}
    body.update(tamper)
    return api.post("/v1/auth/callback", json=body)


def session_de(api, google, email) -> dict[str, str]:
    r = connexion(api, google, email)
    assert r.status_code == 200, r.text
    return {"X-Staff-Session": r.json()["session"]}


def journal() -> list[tuple[str, str | None]]:
    with get_sessionmaker()() as s:
        return [(a.action, a.target) for a in s.scalars(select(AuditLog).order_by(AuditLog.id))]


# --- T09 : aucune route du staff sans contrôle de rôle -------------------------------------


def test_chaque_route_non_publique_exige_un_role(auth_settings):
    app = create_app(auth_settings)

    def roles_of(dependant) -> list:
        found = [getattr(dependant.call, "snacki_roles", None)]
        for sub in dependant.dependencies:
            found += roles_of(sub)
        return [r for r in found if r]

    for route in app.routes:
        if isinstance(route, APIRoute) and route.path not in PUBLIC_ROUTES:
            assert roles_of(route.dependant), f"{route.path} n'a pas de contrôle de rôle"


# --- T10 : connexion Google ---------------------------------------------------------------


def test_connexion_reussie_avec_pkce(api, google):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    r = connexion(api, google, "Aicha@Gmail.com")
    assert r.status_code == 200
    assert r.json()["staff"]["role"] == "caissier"
    # Le vérificateur envoyé à Google correspond bien au défi S256 de l'adresse d'autorisation.
    digest = hashlib.sha256(google.last_verifier.encode()).digest()
    assert base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == google.challenge
    me = api.get("/v1/staff/me", headers={"X-Staff-Session": r.json()["session"]})
    assert me.json() == {
        "id": 1,
        "email": "aicha@gmail.com",
        "display_name": "Aïcha",
        "role": "caissier",
    }
    assert ("login", None) in journal()


def test_adresse_de_connexion_complete(api):
    url = api.post("/v1/auth/start").json()["authorization_url"]
    query = parse_qs(urlsplit(url).query)
    assert url.startswith("https://accounts.google.com/")
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://web.test/auth/callback"]
    assert query["scope"] == ["openid email profile"]
    assert len(query["state"][0]) >= 32 and len(query["nonce"][0]) >= 32


def refuse(r) -> None:
    assert r.status_code == 401
    assert r.json() == {"detail": "Connexion refusée"}


def test_adresse_hors_equipe_refusee(api, google):
    refuse(connexion(api, google, "inconnu@gmail.com"))
    assert journal() == [("login_refused", "inconnu@gmail.com")]


def test_compte_desactive_refuse(api, google):
    membre("ancien@gmail.com", StaffRole.CAISSIER, active=False)
    refuse(connexion(api, google, "ancien@gmail.com"))


@pytest.mark.parametrize(
    "claims",
    [
        {"email_verified": False},
        {"aud": "autre-client.apps.googleusercontent.com"},
        {"iss": "https://faux-google.example"},
        {"exp": datetime.now(UTC) - timedelta(minutes=5)},
    ],
)
def test_jeton_google_invalide(api, google, claims):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    google.claims = claims
    refuse(connexion(api, google, "aicha@gmail.com"))


def test_jeton_signe_par_une_autre_cle(api, google):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    google.key = OTHER_KEY
    refuse(connexion(api, google, "aicha@gmail.com"))


def test_jeton_hs256_forge_avec_la_cle_publique(api, google):
    """Attaque classique : signer en HS256 avec la clé publique. L'algorithme est imposé."""
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    google.algorithm, google.key = "HS256", "cle-publique-detournee-assez-longue-pour-hs256"
    refuse(connexion(api, google, "aicha@gmail.com"))


def test_nonce_rejoue(api, google):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    refuse(connexion(api, google, "aicha@gmail.com", nonce="nonce-d-une-autre-connexion"))


def test_state_different_csrf_de_connexion(api, google):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    refuse(connexion(api, google, "aicha@gmail.com", state="A" * 32))


def test_parcours_falsifie_ou_expire(api, google, auth_settings):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    refuse(connexion(api, google, "aicha@gmail.com", flow="a" * 40 + "." + "b" * 40))
    vieux = jwt.encode(
        {"aud": auth.FLOW_AUDIENCE, "exp": datetime.now(UTC) - timedelta(seconds=1)},
        auth_settings.session_secret.get_secret_value(),
    )
    refuse(connexion(api, google, "aicha@gmail.com", flow=vieux))


def test_champs_inattendus_refuses(api):
    r = api.post(
        "/v1/auth/callback",
        json={"code": "x" * 20, "state": "A" * 32, "flow": "a.b.c" * 5, "role": "admin"},
    )
    assert r.status_code == 422


def test_connexion_non_configuree(client):
    assert client.post("/v1/auth/start").status_code == 503


def test_limite_de_debit_connexion(api):
    for _ in range(10):
        api.post("/v1/auth/start")
    assert api.post("/v1/auth/start").status_code == 429


def test_reponses_jamais_en_cache(api):
    assert api.post("/v1/auth/start").headers["cache-control"] == "no-store"


# --- T07, T12 : sessions --------------------------------------------------------------------


@pytest.mark.parametrize("token", [None, "", "abc", "a.b.c"])
def test_session_absente_ou_illisible(api, token):
    headers = {"X-Staff-Session": token} if token is not None else {}
    assert api.get("/v1/staff/me", headers=headers).status_code == 401


def test_session_signee_par_une_autre_cle(api):
    staff_id = membre("aicha@gmail.com", StaffRole.ADMIN)
    forged = auth.new_session("une-autre-cle-de-32-octets-au-moins!!", staff_id, 1, 8)
    assert api.get("/v1/staff/me", headers={"X-Staff-Session": forged}).status_code == 401


def test_session_sans_signature_refusee(api):
    """Jeton « alg: none » : PyJWT n'accepte que l'algorithme imposé (ASVS V9.1.2)."""
    staff_id = membre("aicha@gmail.com", StaffRole.ADMIN)
    unsigned = jwt.encode(
        {"aud": auth.SESSION_AUDIENCE, "sub": str(staff_id), "ver": 1, "exp": 9999999999},
        None,
        algorithm="none",
    )
    assert api.get("/v1/staff/me", headers={"X-Staff-Session": unsigned}).status_code == 401


def test_session_expiree(api, auth_settings):
    staff_id = membre("aicha@gmail.com", StaffRole.ADMIN)
    secret = auth_settings.session_secret.get_secret_value()
    old = jwt.encode(
        {
            "aud": auth.SESSION_AUDIENCE,
            "sub": str(staff_id),
            "ver": 1,
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        secret,
    )
    assert api.get("/v1/staff/me", headers={"X-Staff-Session": old}).status_code == 401


def test_deconnexion_invalide_la_session(api, google):
    membre("aicha@gmail.com", StaffRole.CAISSIER)
    h = session_de(api, google, "aicha@gmail.com")
    assert api.post("/v1/auth/logout", headers=h).status_code == 204
    assert api.get("/v1/staff/me", headers=h).status_code == 401


def test_desactivation_immediate(api, google):
    membre("admin@gmail.com", StaffRole.ADMIN)
    caissier = membre("caisse@gmail.com", StaffRole.CAISSIER)
    admin = session_de(api, google, "admin@gmail.com")
    h = session_de(api, google, "caisse@gmail.com")
    assert api.get("/v1/staff/me", headers=h).status_code == 200
    r = api.patch(f"/v1/staff/{caissier}", json={"active": False}, headers=admin)
    assert r.status_code == 200
    assert api.get("/v1/staff/me", headers=h).status_code == 401


def test_changement_de_role_immediat(api, google):
    membre("admin@gmail.com", StaffRole.ADMIN)
    gerante = membre("gerante@gmail.com", StaffRole.GERANTE)
    admin = session_de(api, google, "admin@gmail.com")
    h = session_de(api, google, "gerante@gmail.com")
    api.patch(f"/v1/staff/{gerante}", json={"role": "caissier"}, headers=admin)
    assert api.get("/v1/staff/me", headers=h).status_code == 401


# --- T09 : rôles -----------------------------------------------------------------------------


@pytest.mark.parametrize("role", [StaffRole.CAISSIER, StaffRole.GERANTE])
def test_gestion_equipe_reservee_admin(api, google, role):
    membre("membre@gmail.com", role)
    h = session_de(api, google, "membre@gmail.com")
    assert api.get("/v1/staff", headers=h).status_code == 403
    r = api.post("/v1/staff", json={"email": "x@gmail.com", "role": "admin"}, headers=h)
    assert r.status_code == 403
    assert api.patch("/v1/staff/1", json={"role": "admin"}, headers=h).status_code == 403
    assert ("access_denied", "GET /v1/staff") in journal()


def test_admin_gere_l_equipe(api, google):
    membre("admin@gmail.com", StaffRole.ADMIN)
    h = session_de(api, google, "admin@gmail.com")
    r = api.post("/v1/staff", json={"email": " Caisse@Gmail.com ", "role": "caissier"}, headers=h)
    assert r.status_code == 201 and r.json()["email"] == "caisse@gmail.com"
    again = api.post("/v1/staff", json={"email": "caisse@gmail.com", "role": "admin"}, headers=h)
    assert again.status_code == 409
    emails = [u["email"] for u in api.get("/v1/staff", headers=h).json()]
    assert emails == ["caisse@gmail.com", "admin@gmail.com"]
    assert ("staff_added", "caisse@gmail.com") in journal()


@pytest.mark.parametrize("change", [{"role": "gerante"}, {"active": False}])
def test_admin_ne_peut_pas_se_retirer_ses_droits(api, google, change):
    admin_id = membre("admin@gmail.com", StaffRole.ADMIN)
    h = session_de(api, google, "admin@gmail.com")
    assert api.patch(f"/v1/staff/{admin_id}", json=change, headers=h).status_code == 409


def test_un_admin_peut_desactiver_un_autre_admin(api, google):
    membre("admin@gmail.com", StaffRole.ADMIN)
    autre = membre("admin2@gmail.com", StaffRole.ADMIN)
    h = session_de(api, google, "admin@gmail.com")
    assert api.patch(f"/v1/staff/{autre}", json={"active": False}, headers=h).status_code == 200


@pytest.mark.parametrize(
    "body", [{}, {"role": "root"}, {"active": "oui"}, {"role": "admin", "email": "x@y.zz"}]
)
def test_modification_invalide(api, google, body):
    membre("admin@gmail.com", StaffRole.ADMIN)
    h = session_de(api, google, "admin@gmail.com")
    assert api.patch("/v1/staff/1", json=body, headers=h).status_code == 422


# --- Premier administrateur et configuration ------------------------------------------------


def test_premier_admin_cree_une_seule_fois():
    with get_sessionmaker()() as s:
        assert staff.ensure_bootstrap_admin(s, " Mike@Gmail.com ") is True
        s.commit()
        assert staff.ensure_bootstrap_admin(s, "autre@gmail.com") is False
        s.commit()
        assert [u.email for u in s.scalars(select(StaffUser))] == ["mike@gmail.com"]


def test_staging_exige_la_configuration_de_connexion():
    url = "postgresql://u:p@h/db?sslmode=require"
    with pytest.raises(ValidationError, match="SNACKI_SESSION_SECRET"):
        Settings(_env_file=None, environment="staging", database_url=url)
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            _env_file=None,
            environment="prod",
            database_url=url,
            **{
                "session_secret": "k" * 40,
                "oauth_client_id": "id",
                "oauth_client_secret": "secret-de-test",
                "oauth_redirect_uri": "http://web/auth/callback",
            },
        )
