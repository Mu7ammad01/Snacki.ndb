"""J8 : pilotage (gérante et admin seulement) et conservation des données."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text

from snacki_api import auth, retention
from snacki_api.db import get_sessionmaker
from snacki_api.models import AuditLog, HistoryItem, HistorySale, Order, StaffRole, StaffUser

SECRET = "k" * 48
URL = "/v1/pilotage"


@pytest.fixture(autouse=True)
def base_vide():
    with get_sessionmaker()() as s:
        s.execute(
            text(
                "TRUNCATE history_item, history_sale, audit_log, staff_user, order_line, orders "
                "RESTART IDENTITY CASCADE"
            )
        )
        s.commit()


@pytest.fixture
def api(settings) -> TestClient:
    from snacki_api.main import create_app

    configured = settings.model_copy(
        update={
            "oauth_client_id": "client-test",
            "oauth_client_secret": SecretStr("secret-de-test"),
            "oauth_redirect_uri": "https://web.test/auth/callback",
            "session_secret": SecretStr(SECRET),
        }
    )
    return TestClient(create_app(configured))


def membre(role: StaffRole) -> dict[str, str]:
    with get_sessionmaker()() as s:
        user = StaffUser(email=f"{role.value}@gmail.com", role=role)
        s.add(user)
        s.commit()
        return {"X-Staff-Session": auth.new_session(SECRET, user.id, user.session_version, 8)}


def vendre(api, h, items, *, payer=True, **body):
    """Vente au comptoir (déjà acceptée), encaissée ou non."""
    payload = {"items": [{"product_id": p, "quantity": q} for p, q in items], **body}
    if payer:
        payload["paid_method"] = "cash"
    r = api.post("/v1/caisse/orders", json=payload, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def historique(day: date, total: int, items):
    with get_sessionmaker()() as s:
        s.add(
            HistorySale(
                service_day=day,
                ref=f"cmd{total}",
                raw_text="x",
                total_mru=total,
                batch="test",
                items=[
                    HistoryItem(product_id=p, label=p or "dessert", quantity=q) for p, q in items
                ],
            )
        )
        s.commit()


TODAY = datetime.now(UTC).date()


def test_caissier_refuse_et_journalise(api):
    h = membre(StaffRole.CAISSIER)
    assert api.get(URL, headers=h).status_code == 403
    with get_sessionmaker()() as s:
        assert s.scalar(select(AuditLog.action)) == "access_denied"


def test_sans_session(api):
    assert api.get(URL).status_code == 401


def test_chiffres_du_jour_et_de_l_historique(api):
    h = membre(StaffRole.GERANTE)
    vendre(api, h, [("salade", 2), ("crepe", 1)])  # 320
    vendre(api, h, [("avocat", 1)], payer=False)  # non encaissée : exclue
    historique(TODAY - timedelta(days=3), 440, [("crepe", 2), ("fraise", 2)])
    historique(TODAY - timedelta(days=3), 150, [(None, 1)])
    r = api.get(URL, headers=h)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    d = r.json()
    assert d["revenue_mru"] == 910 and d["orders"] == 3 and d["average_basket_mru"] == 303
    assert d["today_mru"] == 320 and d["all_time_mru"] == 910
    assert d["by_day"][-1] == {
        "day": TODAY.isoformat(),
        "app_mru": 0,
        "comptoir_mru": 320,
        "historique_mru": 0,
        "orders": 1,
    }
    top = {t["label"]: (t["quantity"], t["revenue_mru"]) for t in d["top"]}
    assert top["Crêpe"] == (3, 120) and top["Salade de fruits"] == (2, 200)
    assert top["Hors menu"] == (1, 0)
    assert d["payments"] == [{"method": "cash", "count": 1, "amount_mru": 320}]
    assert d["history_first"] == (TODAY - timedelta(days=3)).isoformat()


def test_refusee_et_annulee_exclues(api):
    h = membre(StaffRole.ADMIN)
    o = vendre(api, h, [("salade", 1)])
    oid = 1
    assert (
        api.post(
            f"/v1/caisse/orders/{oid}/cancel", json={"reason": "erreur de saisie"}, headers=h
        ).status_code
        == 200
    )
    assert o["paid_method"] == "cash"
    assert api.get(URL, headers=h).json()["revenue_mru"] == 0


def test_periode_choisie(api):
    h = membre(StaffRole.GERANTE)
    historique(date(2026, 9, 2), 200, [("salade", 2)])
    historique(date(2026, 9, 20), 100, [("avocat", 1)])
    d = api.get(URL, params={"start": "2026-09-01", "end": "2026-09-10"}, headers=h).json()
    assert d["revenue_mru"] == 200 and [p["day"] for p in d["by_day"]] == ["2026-09-02"]
    assert d["all_time_mru"] == 300


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-09-10", "end": "2026-09-01"},
        {"start": "2025-01-01", "end": "2026-09-01"},
        {"start": "hier"},
        {"start": "2026-09-01'; DROP TABLE orders; --"},
    ],
)
def test_periode_invalide(api, params):
    assert api.get(URL, params=params, headers=membre(StaffRole.GERANTE)).status_code == 422


# --- Conservation des données -------------------------------------------------------------


def test_anonymisation_apres_90_jours(api):
    h = membre(StaffRole.ADMIN)
    r = api.post(
        "/v1/orders",
        json={
            "customer_name": "Aïcha",
            "phone": "22123456",
            "fulfilment": "livraison",
            "landmark": "Cansado, maison bleue",
            "note": "sonner deux fois",
            "items": [{"product_id": "salade", "quantity": 1}],
        },
    )
    assert r.status_code == 201
    api.post("/v1/caisse/orders/1/refuse", json={"reason": "test de purge"}, headers=h)
    vendre(api, h, [("crepe", 1)])  # en cours : jamais touchée
    with get_sessionmaker()() as s:
        later = datetime.now(UTC) + timedelta(days=91)
        assert retention.purge(s, 90, now=later)[0] == 1
        o = s.get(Order, 1)
        assert (o.customer_name, o.phone, o.landmark, o.note) == ("Client", None, "—", None)
        assert o.total_mru == 100 and o.anonymized_at is not None
        assert s.get(Order, 2).customer_name == "Comptoir"
        assert retention.purge(s, 90, now=later)[0] == 0  # déjà fait


def test_rien_avant_le_delai(api):
    h = membre(StaffRole.ADMIN)
    vendre(api, h, [("crepe", 1)])
    api.post("/v1/caisse/orders/1/status", json={"status": "prete"}, headers=h)
    api.post("/v1/caisse/orders/1/status", json={"status": "livree"}, headers=h)
    with get_sessionmaker()() as s:
        assert retention.purge(s, 90)[0] == 0


def test_journal_garde_un_an():
    with get_sessionmaker()() as s:
        old = datetime.now(UTC) - timedelta(days=400)
        s.add_all([AuditLog(action="login", at=old), AuditLog(action="login")])
        s.commit()
        assert retention.purge(s, 90)[1] == 1
