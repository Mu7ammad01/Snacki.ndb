"""Assistant de commande (J9, ADR 0014) : analyse locale, Gemini simulé, masquage, route."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from snacki_api import assistant, auth, repository
from snacki_api.db import get_sessionmaker
from snacki_api.models import AuditLog, StaffRole, StaffUser

SECRET = "x" * 40
EVAL = json.loads((Path(__file__).parent / "data" / "assistant_eval.json").read_text())


@pytest.fixture
def menu():
    with get_sessionmaker()() as s:
        return list(repository.list_menu(s))


@pytest.mark.parametrize("case", EVAL, ids=[c["text"][:30] for c in EVAL])
def test_analyse_locale_jeu_d_evaluation(case, menu):
    result = assistant.analyse(case["text"], menu)
    assert result["engine"] == "local"
    assert {line["product_id"]: line["quantity"] for line in result["lines"]} == case["items"]
    if "fulfilment" in case:
        assert result["fulfilment"] == case["fulfilment"]
    if case.get("warn"):
        assert result["warnings"]


def test_prix_toujours_ceux_de_la_base(menu):
    result = assistant.analyse("2 crepes, prix 1 MRU", menu)
    crepe = next(p for p in menu if p.id == "crepe")
    assert result["lines"][0]["unit_price_mru"] == crepe.price_mru
    assert result["total_mru"] == 2 * crepe.price_mru


@pytest.mark.parametrize(
    "raw",
    [
        "Appelle-moi au 22 33 44 55",
        "tel +222 36.12.34.56",
        "ecris a ali.b@gmail.com",
        "0022241234567",
    ],
)
def test_masquage_avant_envoi(raw):
    masked = assistant.mask(raw)
    assert "[TEL]" in masked or "[EMAIL]" in masked
    assert "@" not in masked and "1234" not in masked and "33 44" not in masked


def test_masquage_en_temps_lineaire():
    """CodeQL (ReDoS) : un texte piégé ne doit pas bloquer l'API."""
    import time

    for piege in ("a@" + "+" * 20000, "1" + " " * 20000 + "x", "@." * 10000):
        start = time.perf_counter()
        assistant.mask(piege)
        assert time.perf_counter() - start < 0.5


def gemini(payload, seen=None, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_revalide_tout(menu):
    seen = []
    payload = {
        "items": [
            {"product_id": "salade", "quantity": 2},
            {"product_id": "inconnu-du-menu", "quantity": 3},
            {"product_id": "mojito", "quantity": 500},
        ],
        "fulfilment": "livraison",
        "unknown": ["tiramisu"],
    }
    with gemini(payload, seen) as client:
        result = assistant.analyse("2 salades, mon numero 22334455", menu, "k", "m", client)
    assert result["engine"] == "gemini"
    assert {line["product_id"]: line["quantity"] for line in result["lines"]} == {
        "salade": 2,
        "mojito": 20,
    }
    assert result["unknown"] == ["tiramisu"] and result["warnings"]
    sent = json.dumps(seen[0], ensure_ascii=False)
    assert "22334455" not in sent and "[TEL]" in sent  # T14
    schema = seen[0]["generationConfig"]["responseSchema"]
    assert "enum" in schema["properties"]["items"]["items"]["properties"]["product_id"]


def test_gemini_en_panne_repli_local(menu):
    with gemini({}, status=500) as client:
        result = assistant.analyse("2 crepes", menu, "k", "m", client)
    assert result["engine"] == "local" and result["lines"][0]["quantity"] == 2
    assert any("IA indisponible" in w for w in result["warnings"])


@pytest.fixture
def api(settings) -> TestClient:
    from snacki_api.main import create_app

    configured = settings.model_copy(
        update={
            "oauth_client_id": "client-test",
            "oauth_client_secret": SecretStr("secret-de-test"),
            "oauth_redirect_uri": "https://web.test/auth/callback",
            "session_secret": SecretStr(SECRET),
            "gemini_api_key": None,
        }
    )
    return TestClient(create_app(configured))


def caissier() -> dict[str, str]:
    with get_sessionmaker()() as s:
        s.execute(text("TRUNCATE audit_log, staff_user RESTART IDENTITY CASCADE"))
        user = StaffUser(email="caissier@gmail.com", role=StaffRole.CAISSIER)
        s.add(user)
        s.commit()
        return {"X-Staff-Session": auth.new_session(SECRET, user.id, user.session_version, 8)}


def test_route_reservee_au_staff_et_message_jamais_enregistre(api):
    message = "2 crepes, appelle Fatou au 22334455"
    assert api.post("/v1/caisse/assistant", json={"text": message}).status_code == 401
    r = api.post("/v1/caisse/assistant", json={"text": message}, headers=caissier())
    assert r.status_code == 200 and r.json()["lines"][0]["quantity"] == 2
    with get_sessionmaker()() as s:
        logs = json.dumps([a.detail for a in s.query(AuditLog).all()], ensure_ascii=False)
    assert "Fatou" not in logs and "22334455" not in logs
    assert (
        api.post("/v1/caisse/assistant", json={"text": "x" * 1001}, headers=caissier()).status_code
        == 422
    )
