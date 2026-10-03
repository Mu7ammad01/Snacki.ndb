"""J7 : caisse — machine à états des commandes, rôles, comptoir, encaissement, journal (T11)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text

from snacki_api import auth
from snacki_api.db import get_sessionmaker
from snacki_api.main import create_app
from snacki_api.models import AuditLog, StaffRole, StaffUser

TRACK = "/v1/orders/track"
SECRET = "k" * 48


@pytest.fixture(autouse=True)
def base_vide():
    with get_sessionmaker()() as s:
        s.execute(
            text("TRUNCATE audit_log, staff_user, order_line, orders RESTART IDENTITY CASCADE")
        )
        s.commit()


@pytest.fixture
def api(settings) -> TestClient:
    configured = settings.model_copy(
        update={
            "oauth_client_id": "client-test",
            "oauth_client_secret": SecretStr("secret-de-test"),
            "oauth_redirect_uri": "https://web.test/auth/callback",
            "session_secret": SecretStr(SECRET),
        }
    )
    return TestClient(create_app(configured))


def membre(role: StaffRole, email: str | None = None) -> dict[str, str]:
    with get_sessionmaker()() as s:
        user = StaffUser(email=email or f"{role.value}@gmail.com", role=role)
        s.add(user)
        s.commit()
        token = auth.new_session(SECRET, user.id, user.session_version, 8)
    return {"X-Staff-Session": token}


def commande_client(api: TestClient, **changes) -> dict:
    body = {
        "customer_name": "Aïcha",
        "phone": "22123456",
        "fulfilment": "emporter",
        "items": [{"product_id": "salade", "quantity": 2}, {"product_id": "crepe", "quantity": 1}],
        **changes,
    }
    r = api.post("/v1/orders", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def journal() -> list[str]:
    with get_sessionmaker()() as s:
        return list(s.scalars(select(AuditLog.action).order_by(AuditLog.id)))


def action(api, h, order_id, name, body=None):
    return api.post(f"/v1/caisse/orders/{order_id}/{name}", json=body, headers=h)


@pytest.fixture
def caissier():
    return membre(StaffRole.CAISSIER)


@pytest.fixture
def gerante():
    return membre(StaffRole.GERANTE)


# --- Commandes du jour ----------------------------------------------------------------------


def test_la_caisse_voit_les_commandes_du_jour_avec_les_coordonnees(api, caissier):
    commande_client(api, note="moins sucré", pay_pref="bankily")
    r = api.get("/v1/caisse/orders", headers=caissier)
    assert r.status_code == 200
    (order,) = r.json()["orders"]
    assert order["customer_name"] == "Aïcha" and order["phone"] == "22123456"
    assert order["note"] == "moins sucré" and order["pay_pref"] == "bankily"
    assert order["status"] == "recue" and order["grand_total_mru"] == 320
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-type"] == "application/json; charset=utf-8"  # V4.1.1


def test_sans_session_rien_n_est_visible(api):
    commande_client(api)
    assert api.get("/v1/caisse/orders").status_code == 401


@pytest.mark.parametrize(
    "champ", [{"note": "a\nb"}, {"pay_pref": "carte"}, {"note": "x" * 201}, {"delivery_fee_mru": 0}]
)
def test_commande_client_champs_controles(api, champ):
    body = {
        "customer_name": "Aïcha",
        "phone": "22123456",
        "fulfilment": "emporter",
        "items": [{"product_id": "salade", "quantity": 1}],
        **champ,
    }
    assert api.post("/v1/orders", json=body).status_code == 422


# --- Machine à états (ASVS V2.3.1) ------------------------------------------------------------


def test_parcours_complet_a_emporter(api, caissier):
    o = commande_client(api)
    oid = 1
    r = action(api, caissier, oid, "accept", {"ready_in_min": 15})
    assert r.status_code == 200 and r.json()["status"] == "acceptee" and r.json()["ready_at"]
    for target in ("en_preparation", "prete", "livree"):
        r = action(api, caissier, oid, "status", {"status": target})
        assert r.status_code == 200, r.text
    suivi = api.get(TRACK, headers={"X-Tracking-Token": o["tracking_token"]}).json()
    assert suivi["status"] == "livree" and suivi["ready_at"]
    assert "phone" not in suivi and "customer_name" not in suivi  # le suivi reste anonyme (T03)
    assert journal() == ["order_accepted", "order_status", "order_status", "order_status"]


@pytest.mark.parametrize(
    "steps",
    [
        [("status", {"status": "prete"})],  # sauter des étapes
        [("accept", {"ready_in_min": 10}), ("accept", {"ready_in_min": 10})],  # deux fois
        [("accept", {"ready_in_min": 10}), ("status", {"status": "livree"})],
        [("accept", {"ready_in_min": 10}), ("status", {"status": "recue"})],  # revenir en arrière
        [("called", None)],  # appeler avant d'accepter
    ],
)
def test_transitions_interdites(api, caissier, steps):
    commande_client(api)
    *before, (name, body) = steps
    for n, b in before:
        assert action(api, caissier, 1, n, b).status_code == 200
    assert action(api, caissier, 1, name, body).status_code == 409


@pytest.mark.parametrize("delai", [0, 4, 121])
def test_delai_borne(api, caissier, delai):
    commande_client(api)
    assert action(api, caissier, 1, "accept", {"ready_in_min": delai}).status_code == 422


def test_frais_de_livraison_fixes_par_le_staff(api, caissier):
    o = commande_client(api, fulfilment="livraison", landmark="Cansado — près de la mosquée")
    assert action(api, caissier, 1, "accept", {"ready_in_min": 30}).status_code == 409
    r = action(api, caissier, 1, "accept", {"ready_in_min": 30, "delivery_fee_mru": 50})
    assert r.json()["grand_total_mru"] == 370
    suivi = api.get(TRACK, headers={"X-Tracking-Token": o["tracking_token"]}).json()
    assert (suivi["delivery_fee_mru"], suivi["grand_total_mru"]) == (50, 370)


def test_pas_de_frais_a_emporter(api, caissier):
    commande_client(api)
    r = action(api, caissier, 1, "accept", {"ready_in_min": 10, "delivery_fee_mru": 50})
    assert r.status_code == 409


def test_livraison_exige_l_appel_au_client(api, caissier):
    commande_client(api, fulfilment="livraison", landmark="Numerowatt, maison bleue")
    action(api, caissier, 1, "accept", {"ready_in_min": 30, "delivery_fee_mru": 0})
    action(api, caissier, 1, "status", {"status": "en_preparation"})
    action(api, caissier, 1, "status", {"status": "prete"})
    assert action(api, caissier, 1, "status", {"status": "livree"}).status_code == 409
    assert action(api, caissier, 1, "called").status_code == 200
    assert action(api, caissier, 1, "status", {"status": "livree"}).status_code == 200


def test_commande_inconnue(api, caissier):
    assert action(api, caissier, 999, "accept", {"ready_in_min": 10}).status_code == 404


# --- Refus et annulation : gérante ou admin -------------------------------------------------


def test_le_caissier_ne_peut_ni_refuser_ni_annuler(api, caissier):
    commande_client(api)
    assert action(api, caissier, 1, "refuse", {"reason": "fausse commande"}).status_code == 403
    action(api, caissier, 1, "accept", {"ready_in_min": 10})
    assert action(api, caissier, 1, "cancel", {"reason": "client absent"}).status_code == 403
    assert journal().count("access_denied") == 2


def test_la_gerante_refuse_une_commande_recue(api, gerante):
    o = commande_client(api)
    r = action(api, gerante, 1, "refuse", {"reason": "Rupture d'avocats"})
    assert r.json()["status"] == "refusee"
    suivi = api.get(TRACK, headers={"X-Tracking-Token": o["tracking_token"]}).json()
    assert suivi["status"] == "refusee" and suivi["closed_reason"] == "Rupture d'avocats"
    assert action(api, gerante, 1, "accept", {"ready_in_min": 10}).status_code == 409


def test_refus_apres_acceptation_impossible_il_faut_annuler(api, gerante):
    commande_client(api)
    action(api, gerante, 1, "accept", {"ready_in_min": 10})
    assert action(api, gerante, 1, "refuse", {"reason": "trop tard"}).status_code == 409
    r = action(api, gerante, 1, "cancel", {"reason": "client injoignable"})
    assert r.status_code == 200 and r.json()["status"] == "annulee"


def test_admin_annule_et_le_journal_garde_le_motif(api):
    admin = membre(StaffRole.ADMIN)
    commande_client(api)
    action(api, admin, 1, "accept", {"ready_in_min": 10})
    action(api, admin, 1, "pay", {"method": "cash"})
    action(api, admin, 1, "cancel", {"reason": "erreur de saisie"})
    with get_sessionmaker()() as s:
        last = s.scalars(select(AuditLog).order_by(AuditLog.id.desc())).first()
    assert last.action == "order_cancelled"
    assert last.detail["motif"] == "erreur de saisie" and last.detail["deja_payee"] is True


@pytest.mark.parametrize("reason", ["", "ok", "a\nb", "x" * 161])
def test_motif_obligatoire_et_controle(api, gerante, reason):
    commande_client(api)
    assert action(api, gerante, 1, "refuse", {"reason": reason}).status_code == 422


def test_commande_remise_ne_s_annule_plus(api, gerante):
    commande_client(api)
    action(api, gerante, 1, "accept", {"ready_in_min": 10})
    for target in ("en_preparation", "prete", "livree"):
        action(api, gerante, 1, "status", {"status": target})
    assert action(api, gerante, 1, "cancel", {"reason": "trop tard"}).status_code == 409


# --- Encaissement et comptoir ---------------------------------------------------------------


def test_encaissement_unique(api, caissier):
    commande_client(api)
    assert action(api, caissier, 1, "pay", {"method": "cash"}).status_code == 409  # pas acceptée
    action(api, caissier, 1, "accept", {"ready_in_min": 10})
    r = action(api, caissier, 1, "pay", {"method": "bankily"})
    assert r.json()["paid_method"] == "bankily" and r.json()["paid_at"]
    assert action(api, caissier, 1, "pay", {"method": "cash"}).status_code == 409
    assert action(api, caissier, 1, "pay", {"method": "carte"}).status_code == 422


def test_vente_au_comptoir(api, caissier):
    commande_client(api)
    r = api.post(
        "/v1/caisse/orders",
        json={"items": [{"product_id": "avocat", "quantity": 2}], "paid_method": "cash"},
        headers=caissier,
    )
    assert r.status_code == 201
    o = r.json()
    assert o["source"] == "comptoir" and o["status"] == "en_preparation"
    assert o["number"].endswith("-002")  # même numérotation que l'app
    assert o["phone"] is None and o["customer_name"] == "Comptoir"
    assert o["grand_total_mru"] == 200 and o["paid_method"] == "cash"
    assert journal()[-2:] == ["counter_sale", "order_paid"]


@pytest.mark.parametrize(
    "body",
    [
        {"items": [{"product_id": "avocat", "quantity": 1, "unit_price_mru": 1}]},
        {"items": [{"product_id": "avocat", "quantity": 1}], "total_mru": 1},
        {"items": []},
        {"items": [{"product_id": "pizza", "quantity": 1}]},
    ],
)
def test_comptoir_jamais_de_prix_envoye(api, caissier, body):
    assert api.post("/v1/caisse/orders", json=body, headers=caissier).status_code == 422
