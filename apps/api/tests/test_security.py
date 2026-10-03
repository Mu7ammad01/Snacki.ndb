"""Contrôles de sécurité de J2 : injection SQL (T05, ASVS V1.2.4), configuration sans secret,
en-têtes, erreurs sans fuite d'information."""

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from snacki_api.config import Settings
from snacki_api.db import get_sessionmaker
from snacki_api.main import create_app
from snacki_api.models import Product

INJECTIONS = [
    "jus' OR '1'='1",
    "jus'; DROP TABLE product; --",
    "delices UNION SELECT * FROM product",
]


def _count_products() -> int:
    with get_sessionmaker()() as s:
        return s.scalar(select(func.count()).select_from(Product))


@pytest.mark.parametrize("payload", INJECTIONS)
def test_injection_dans_la_categorie_refusee(client, payload):
    r = client.get("/v1/menu", params={"category": payload})
    assert r.status_code == 422  # valeur hors liste blanche : rejetée avant la base
    assert _count_products() == 9


@pytest.mark.parametrize("payload", ["salade' OR '1'='1", "salade;--", "../etc/passwd", "SALADE"])
def test_injection_dans_l_identifiant_refusee(client, payload):
    r = client.get(f"/v1/menu/{payload}")
    assert r.status_code in (404, 422)
    assert "salade" not in r.text.lower() or r.status_code == 422
    assert _count_products() == 9


def test_valeur_dangereuse_traitee_comme_donnee(client):
    # Même un identifiant au bon format n'est qu'un paramètre lié : aucune erreur SQL, juste 404.
    assert client.get("/v1/menu/or-a-a").status_code == 404


def test_base_obligatoire(monkeypatch):
    monkeypatch.delenv("SNACKI_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secret_absent_des_affichages(settings):
    url = settings.database_url.get_secret_value()
    password = url.split("://", 1)[1].split("@", 1)[0].split(":", 1)[1]
    assert password not in repr(settings)
    assert password not in str(settings.model_dump())


def test_secret_absent_des_erreurs_de_validation():
    # Incident J2 : un mot de passe collé seul apparaissait en clair dans l'erreur pydantic.
    faux_secret = "npg_CeciEstUnFauxSecret"  # noqa: S105 - valeur de test
    with pytest.raises(ValidationError) as err:
        Settings(_env_file=None, database_url=faux_secret)
    assert faux_secret not in str(err.value)
    assert "URL PostgreSQL" in str(err.value)


# Réglages minimaux d'un environnement en ligne (connexion du staff configurée, J6).
PROD_AUTH = {
    "session_secret": "k" * 40,
    "oauth_client_id": "client-test",
    "oauth_client_secret": "secret-de-test",
    "oauth_redirect_uri": "https://web.test/auth/callback",
}


def test_production_exige_tls_vers_la_base():
    with pytest.raises(ValidationError, match="sslmode"):
        Settings(
            _env_file=None, environment="prod", database_url="postgresql://u:p@h/db", **PROD_AUTH
        )
    ok = Settings(
        _env_file=None,
        environment="prod",
        database_url="postgresql://u:p@h/db?sslmode=require",
        **PROD_AUTH,
    )
    assert ok.database_url.get_secret_value().startswith("postgresql+psycopg://")


def test_production_refuse_origine_cors_en_clair():
    with pytest.raises(ValidationError, match="CORS"):
        Settings(
            _env_file=None,
            environment="prod",
            database_url="postgresql://u:p@h/db?sslmode=require",
            cors_origins=["http://snacki.example"],
            **PROD_AUTH,
        )


def test_documentation_masquee_en_production():
    prod = Settings(
        _env_file=None,
        environment="prod",
        database_url="postgresql://u:p@h/db?sslmode=require",
        **PROD_AUTH,
    )
    app = create_app(prod)
    assert app.openapi_url is None and app.docs_url is None


def test_en_tetes_de_securite(client):
    r = client.get("/v1/menu")
    assert r.headers["content-type"] == "application/json; charset=utf-8"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_cors_origine_fixe(settings):
    s = settings.model_copy(update={"cors_origins": ["http://localhost:3000"]})
    from fastapi.testclient import TestClient

    c = TestClient(create_app(s))
    ok = c.get("/v1/menu", headers={"Origin": "http://localhost:3000"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    bad = c.get("/v1/menu", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_erreur_base_sans_detail(settings, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError

    import snacki_api.repository as repo

    def boom(*a, **k):
        raise OperationalError("SELECT secret FROM x", {}, Exception("host=db.internal"))

    monkeypatch.setattr(repo, "list_menu", boom)
    r = TestClient(create_app(settings)).get("/v1/menu")
    assert r.status_code == 503
    assert "secret" not in r.text and "db.internal" not in r.text


def test_sondes(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ok"}
