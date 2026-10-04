"""J8 bis : fidélité — numéros uniques, tampons, cadeau, annulations, anti-fraude (T28)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text

from snacki_api import auth, loyalty, manage
from snacki_api.db import get_sessionmaker
from snacki_api.models import CardStatus, LoyaltyCard, LoyaltyEvent, StaffRole, StaffUser

SECRET = "k" * 48


@pytest.fixture(autouse=True)
def base_vide():
    with get_sessionmaker()() as s:
        s.execute(
            text(
                "TRUNCATE loyalty_event, loyalty_card, audit_log, staff_user, order_line, orders "
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


@pytest.fixture
def caissier():
    return membre(StaffRole.CAISSIER)


@pytest.fixture
def gerante():
    return membre(StaffRole.GERANTE)


def cartes(n=2) -> list[str]:
    with get_sessionmaker()() as s:
        return [loyalty.display(c) for c in loyalty.issue(s, n, "LTEST")]


def vente(api, h, payer=True, items=(("salade", 1),)):
    body = {"items": [{"product_id": p, "quantity": q} for p, q in items]}
    if payer:
        body["paid_method"] = "cash"
    r = api.post("/v1/caisse/orders", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def tamponner(api, h, oid, code, **extra):
    return api.post(f"/v1/caisse/orders/{oid}/loyalty", json={"code": code, **extra}, headers=h)


def vieillir(minutes=11):
    """Recule le dernier tampon pour passer le délai minimal entre deux tampons."""
    with get_sessionmaker()() as s:
        for card in s.scalars(select(LoyaltyCard)):
            if card.last_stamp_at:
                card.last_stamp_at -= timedelta(minutes=minutes)
        for ev in s.scalars(select(LoyaltyEvent)):
            ev.at -= timedelta(days=1)
        s.commit()


# --- Numéros ------------------------------------------------------------------------------


def test_numeros_uniques_avec_controle():
    codes = {loyalty.new_code() for _ in range(2000)}
    assert len(codes) == 2000
    for c in list(codes)[:50]:
        assert loyalty.normalize(c) == c
        assert loyalty.normalize(loyalty.display(c).lower()) == c


def test_une_faute_de_frappe_est_detectee():
    c = loyalty.new_code()
    for i in range(8):
        for ch in loyalty.ALPHABET:
            if ch != c[i]:
                assert loyalty.normalize(c[:i] + ch + c[i + 1 :]) is None


@pytest.mark.parametrize(
    "raw",
    ["https://snacki.test/carte#FID-{a}-{b}", "fid {a} {b}", "FID-{a}-{b}", "{a}{b}"],
)
def test_lecture_du_qr_et_de_la_saisie(raw):
    c = loyalty.new_code()
    assert loyalty.normalize(raw.format(a=c[:4], b=c[4:])) == c


def test_confusions_courantes_corrigees():
    body = "0000001"  # que des zéros et un un
    code = body + loyalty._check_char(body)
    assert loyalty.normalize("OOOOOOI" + code[7]) == code


@pytest.mark.parametrize("raw", ["", "FID-1234", "x" * 300, "FID-ABCD-EFGU", None])
def test_numeros_invalides(raw):
    assert loyalty.normalize(raw) is None


# --- Tampons ------------------------------------------------------------------------------


def test_cinq_tampons_puis_cadeau(api, caissier):
    (code,) = cartes(1)
    for _ in range(5):
        oid = vente(api, caissier)
        r = tamponner(api, caissier, oid, code)
        assert r.status_code == 200, r.text
        vieillir()
    info = api.post("/v1/caisse/loyalty", json={"code": code}, headers=caissier).json()
    assert (info["stamps"], info["rewards_available"], info["status"]) == (5, 1, "active")
    oid = vente(api, caissier, payer=False, items=(("crepe", 1), ("salade", 1)))
    r = api.post(f"/v1/caisse/orders/{oid}/reward", json={"code": code}, headers=caissier)
    assert r.status_code == 200 and r.json()["discount_mru"] == 100
    assert r.json()["grand_total_mru"] == 120  # 220 − 100
    info = api.post("/v1/caisse/loyalty", json={"code": code}, headers=caissier).json()
    assert (info["stamps"], info["rewards_taken"]) == (0, 1)


def test_tampon_seulement_apres_encaissement(api, caissier):
    (code,) = cartes(1)
    oid = vente(api, caissier, payer=False)
    assert tamponner(api, caissier, oid, code).status_code == 409


def test_une_commande_un_seul_tampon(api, caissier):
    a, b = cartes(2)
    oid = vente(api, caissier)
    assert tamponner(api, caissier, oid, a).status_code == 200
    assert tamponner(api, caissier, oid, a).status_code == 409
    assert tamponner(api, caissier, oid, b).status_code == 409


def test_delai_entre_deux_tampons(api, caissier):
    (code,) = cartes(1)
    assert tamponner(api, caissier, vente(api, caissier), code).status_code == 200
    r = tamponner(api, caissier, vente(api, caissier), code)
    assert r.status_code == 409 and "10 minutes" in r.json()["detail"]


def test_trois_tampons_par_jour(api, caissier):
    (code,) = cartes(1)
    for _ in range(3):
        assert tamponner(api, caissier, vente(api, caissier), code).status_code == 200
        with get_sessionmaker()() as s:  # recule seulement le délai, pas le jour
            card = s.scalars(select(LoyaltyCard)).one()
            card.last_stamp_at -= timedelta(minutes=11)
            s.commit()
    r = tamponner(api, caissier, vente(api, caissier), code)
    assert r.status_code == 409 and "3 tampons" in r.json()["detail"]


def test_numero_invente_refuse(api, caissier):
    cartes(1)
    valid_but_unknown = loyalty.display(loyalty.new_code())
    assert tamponner(api, caissier, vente(api, caissier), valid_but_unknown).status_code == 409
    assert tamponner(api, caissier, vente(api, caissier), "FID-AAAA-AAAA").status_code == 409


def test_telephone_facultatif_et_controle(api, caissier):
    (code,) = cartes(1)
    assert tamponner(api, caissier, vente(api, caissier), code, phone="1234").status_code == 422
    assert tamponner(api, caissier, vente(api, caissier), code, phone="22123456").status_code == 200
    info = api.post("/v1/caisse/loyalty", json={"code": code}, headers=caissier).json()
    assert info["phone_linked"] is True


def test_cadeau_refuse_sans_cinq_tampons_ou_deja_paye(api, caissier):
    (code,) = cartes(1)
    oid = vente(api, caissier, payer=False)
    r = api.post(f"/v1/caisse/orders/{oid}/reward", json={"code": code}, headers=caissier)
    assert r.status_code == 409 and "0 tampon" in r.json()["detail"]
    oid = vente(api, caissier)
    assert (
        api.post(
            f"/v1/caisse/orders/{oid}/reward", json={"code": code}, headers=caissier
        ).status_code
        == 409
    )


def test_commande_offerte_sans_tampon(api, caissier):
    (code,) = cartes(1)
    with get_sessionmaker()() as s:
        s.scalars(select(LoyaltyCard)).one().stamps = 5
        s.commit()
    oid = vente(api, caissier, payer=False)
    api.post(f"/v1/caisse/orders/{oid}/reward", json={"code": code}, headers=caissier)
    api.post(f"/v1/caisse/orders/{oid}/pay", json={"method": "cash"}, headers=caissier)
    assert tamponner(api, caissier, oid, code).status_code == 409


# --- Annulations ---------------------------------------------------------------------------


def test_annulation_retire_le_tampon(api, caissier, gerante):
    (code,) = cartes(1)
    oid = vente(api, caissier)
    tamponner(api, caissier, oid, code)
    api.post(
        f"/v1/caisse/orders/{oid}/cancel", json={"reason": "erreur de caisse"}, headers=gerante
    )
    info = api.post("/v1/caisse/loyalty", json={"code": code}, headers=caissier).json()
    assert info["stamps"] == 0


def test_annulation_du_cadeau_rend_les_tampons(api, caissier, gerante):
    (code,) = cartes(1)
    with get_sessionmaker()() as s:
        s.scalars(select(LoyaltyCard)).one().stamps = 5
        s.commit()
    oid = vente(api, caissier, payer=False)
    api.post(f"/v1/caisse/orders/{oid}/reward", json={"code": code}, headers=caissier)
    api.post(f"/v1/caisse/orders/{oid}/cancel", json={"reason": "client parti"}, headers=gerante)
    info = api.post("/v1/caisse/loyalty", json={"code": code}, headers=caissier).json()
    assert (info["stamps"], info["rewards_taken"]) == (5, 0)


# --- Gérante : blocage, transfert, recherche -------------------------------------------------


def test_carte_bloquee(api, caissier, gerante):
    (code,) = cartes(1)
    assert (
        api.post(
            "/v1/loyalty/block", json={"code": code, "reason": "carte volée"}, headers=caissier
        ).status_code
        == 403
    )
    r = api.post("/v1/loyalty/block", json={"code": code, "reason": "carte volée"}, headers=gerante)
    assert r.json()["status"] == "blocked"
    r = tamponner(api, caissier, vente(api, caissier), code)
    assert r.status_code == 409 and "bloquée" in r.json()["detail"]


def test_carte_perdue_transferee(api, caissier, gerante):
    old, new = cartes(2)
    tamponner(api, caissier, vente(api, caissier), old, phone="22123456")
    r = api.post("/v1/loyalty/search", json={"phone": "22123456"}, headers=gerante)
    assert [c["card"] for c in r.json()] == [old]
    r = api.post("/v1/loyalty/transfer", json={"old_code": old, "new_code": new}, headers=gerante)
    assert r.status_code == 200 and r.json()["stamps"] == 1 and r.json()["phone_linked"]
    again = api.post(
        "/v1/loyalty/transfer", json={"old_code": old, "new_code": new}, headers=gerante
    )
    assert again.status_code == 409
    with get_sessionmaker()() as s:
        assert (
            s.scalars(select(LoyaltyCard).where(LoyaltyCard.id == 1)).one().status
            == CardStatus.BLOCKED
        )


# --- Client -------------------------------------------------------------------------------


def test_suivi_public_sans_donnee_personnelle(api, caissier):
    (code,) = cartes(1)
    tamponner(api, caissier, vente(api, caissier), code, phone="22123456")
    r = api.post("/v1/loyalty/status", json={"code": code})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.json() == {
        "card": code,
        "status": "active",
        "progress": 1,
        "goal": 5,
        "rewards_available": 0,
    }
    assert api.post("/v1/loyalty/status", json={"code": "FID-AAAA-AAAA"}).status_code == 404


def test_suivi_public_limite(api):
    cartes(1)
    statuses = [
        api.post(
            "/v1/loyalty/status", json={"code": loyalty.display(loyalty.new_code())}
        ).status_code
        for _ in range(21)
    ]
    assert statuses[-1] == 429


def test_pilotage_compte_le_cadeau(api, caissier, gerante):
    (code,) = cartes(1)
    tamponner(api, caissier, vente(api, caissier), code)
    with get_sessionmaker()() as s:
        s.scalars(select(LoyaltyCard)).one().stamps = 5
        s.commit()
    oid = vente(api, caissier, payer=False)
    api.post(f"/v1/caisse/orders/{oid}/reward", json={"code": code}, headers=caissier)
    api.post(f"/v1/caisse/orders/{oid}/pay", json={"method": "cash"}, headers=caissier)
    d = api.get("/v1/pilotage", headers=gerante).json()
    assert d["revenue_mru"] == 100  # 100 encaissés + (100 − 100) offerts
    assert d["loyalty"] == {"stamps": 1, "rewards": 1, "discount_mru": 100, "active_cards": 1}


# --- Étiquettes ----------------------------------------------------------------------------


def test_etiquettes_imprimees(tmp_path, capsys):
    out = tmp_path / "cartes.pdf"
    assert (
        manage.main(
            [
                "loyalty-cards",
                "--count",
                "45",
                "--base-url",
                "https://snacki.test",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert (
        out.read_bytes().startswith(b"%PDF")
        and "45 cartes, 23 page(s) A4 (cartes)" in capsys.readouterr().out
    )
    with get_sessionmaker()() as s:
        assert len(s.scalars(select(LoyaltyCard)).all()) == 45


def test_planches_d_etiquettes_et_reimpression(tmp_path, capsys):
    out = tmp_path / "etiquettes.pdf"
    args = ["--base-url", "https://snacki.test", "--out", str(out), "--layout", "etiquettes"]
    assert manage.main(["loyalty-cards", "--count", "45", *args]) == 0
    assert "2 page(s) A4 (etiquettes)" in capsys.readouterr().out
    with get_sessionmaker()() as s:
        batch = s.scalars(select(LoyaltyCard.batch)).first()
    assert manage.main(["loyalty-cards", "--reprint", batch, *args]) == 0
    assert manage.main(["loyalty-cards", "--reprint", "INCONNU", *args]) == 1
    with get_sessionmaker()() as s:
        assert (
            len(s.scalars(select(LoyaltyCard)).all()) == 45
        )  # réimpression : aucune carte en plus


def test_etiquettes_refusent_http(tmp_path):
    out = tmp_path / "cartes.pdf"
    assert (
        manage.main(
            ["loyalty-cards", "--count", "1", "--base-url", "http://snacki.test", "--out", str(out)]
        )
        == 1
    )


def test_telephone_efface_apres_un_an():
    from snacki_api import retention

    (code,) = cartes(1)
    with get_sessionmaker()() as s:
        card = s.scalars(select(LoyaltyCard)).one()
        card.phone, card.last_stamp_at = "22123456", datetime.now(UTC) - timedelta(days=400)
        s.commit()
        retention.purge(s, 90)
        assert s.scalars(select(LoyaltyCard)).one().phone is None
