"""J3 : commande côté serveur (T01), jeton de suivi (T02, T03), limite de débit (T04)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update

from snacki_api.db import get_sessionmaker
from snacki_api.models import Order, Product

TRACK = "/v1/orders/track"


@pytest.fixture(autouse=True)
def tables_vides():
    with get_sessionmaker()() as s:
        s.execute(text("TRUNCATE order_line, orders RESTART IDENTITY CASCADE"))
        s.execute(update(Product).values(available=True))
        s.execute(update(Product).where(Product.id == "salade").values(price_mru=100))
        s.commit()


def commande(**changes):
    body = {
        "customer_name": "Aïcha",
        "phone": "22 12 34 56",
        "fulfilment": "emporter",
        "items": [{"product_id": "salade", "quantity": 2}, {"product_id": "crepe", "quantity": 1}],
    }
    body.update(changes)
    return body


def creer(client, **changes):
    r = client.post("/v1/orders", json=commande(**changes))
    assert r.status_code == 201, r.text
    return r.json()


# --- T01 : le total vient de la base ------------------------------------------------------


def test_total_calcule_par_le_serveur(client):
    body = creer(client)
    assert body["total_mru"] == 2 * 100 + 120
    assert [(li["product_id"], li["line_total_mru"]) for li in body["lines"]] == [
        ("salade", 200),
        ("crepe", 120),
    ]
    assert body["status"] == "recue"


@pytest.mark.parametrize(
    "champ",
    [
        {"total_mru": 1},
        {"price": 0},
        {"items": [{"product_id": "salade", "quantity": 1, "unit_price_mru": 1}]},
    ],
)
def test_prix_envoye_par_le_client_refuse(client, champ):
    r = client.post("/v1/orders", json=commande(**champ))
    assert r.status_code == 422
    with get_sessionmaker()() as s:
        assert s.scalar(select(Order.id)) is None


def test_prix_fige_dans_la_commande(client):
    token = creer(client)["tracking_token"]
    with get_sessionmaker()() as s:
        s.execute(update(Product).where(Product.id == "salade").values(price_mru=150))
        s.commit()
    suivi = client.get(TRACK, headers={"X-Tracking-Token": token}).json()
    assert suivi["total_mru"] == 320


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"product_id": "salade", "quantity": 0}],
        [{"product_id": "salade", "quantity": 21}],
        [{"product_id": "salade", "quantity": 1}, {"product_id": "salade", "quantity": 1}],
        [{"product_id": f"p{'a' * i}", "quantity": 1} for i in range(11)],
        [{"product_id": "SALADE'--", "quantity": 1}],
    ],
)
def test_lignes_invalides(client, items):
    assert client.post("/v1/orders", json=commande(items=items)).status_code == 422


def test_produit_inconnu_ou_indisponible(client):
    r = client.post("/v1/orders", json=commande(items=[{"product_id": "pizza", "quantity": 1}]))
    assert r.status_code == 422
    with get_sessionmaker()() as s:
        s.execute(update(Product).where(Product.id == "crepe").values(available=False))
        s.commit()
    assert client.post("/v1/orders", json=commande()).status_code == 422


@pytest.mark.parametrize("phone", ["1234", "52123456", "2212345", "+33612345678", "22a23456"])
def test_telephone_invalide(client, phone):
    assert client.post("/v1/orders", json=commande(phone=phone)).status_code == 422


@pytest.mark.parametrize("phone", ["+222 22 12 34 56", "0022246123456", "36.12.34.56"])
def test_telephone_normalise(client, phone):
    creer(client, phone=phone)
    with get_sessionmaker()() as s:
        assert s.scalar(select(Order.phone)) in {"22123456", "46123456", "36123456"}


def test_livraison_exige_un_repere(client):
    assert client.post("/v1/orders", json=commande(fulfilment="livraison")).status_code == 422
    creer(client, fulfilment="livraison", landmark="Près de la mosquée de Numerowatt")


@pytest.mark.parametrize("name", ["", "   ", "a" * 41, "Ali\x00", "Ali\nBob"])
def test_prenom_invalide(client, name):
    assert client.post("/v1/orders", json=commande(customer_name=name)).status_code == 422


def test_numeros_du_jour_attribues_par_le_serveur(client):
    a, b = creer(client), creer(client)
    jour = datetime.now(UTC).strftime("%m%d")
    assert (a["number"], b["number"]) == (f"SNK-{jour}-001", f"SNK-{jour}-002")


# --- T02 et T03 : suivi par jeton ----------------------------------------------------------


def test_jeton_aleatoire_stocke_hache(client):
    body = creer(client)
    token = body["tracking_token"]
    assert len(token) >= 22  # 16 octets en base64url
    with get_sessionmaker()() as s:
        stored = s.scalar(select(Order.tracking_hash))
    assert token not in stored and len(stored) == 64


def test_suivi_sans_donnee_personnelle(client):
    token = creer(client, fulfilment="livraison", landmark="Rond-point de Cansado")[
        "tracking_token"
    ]
    r = client.get(TRACK, headers={"X-Tracking-Token": token})
    assert r.status_code == 200
    for secret in ("Aïcha", "22123456", "Cansado", "customer_name", "phone", "landmark"):
        assert secret not in r.text
    assert "tracking_token" not in r.json()


def test_un_jeton_n_ouvre_que_sa_commande(client):
    a, b = creer(client), creer(client)
    ra = client.get(TRACK, headers={"X-Tracking-Token": a["tracking_token"]}).json()
    rb = client.get(TRACK, headers={"X-Tracking-Token": b["tracking_token"]}).json()
    assert (ra["number"], rb["number"]) == (a["number"], b["number"])


@pytest.mark.parametrize("token", ["", "x", "A" * 22, "' OR 1=1--", "a" * 500])
def test_jeton_invalide_meme_reponse(client, token):
    creer(client)
    r = client.get(TRACK, headers={"X-Tracking-Token": token})
    assert r.status_code == 404
    assert r.json() == {"detail": "Commande introuvable ou lien expiré"}


def test_jeton_expire(client):
    token = creer(client)["tracking_token"]
    with get_sessionmaker()() as s:
        s.execute(
            update(Order).values(tracking_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        s.commit()
    assert client.get(TRACK, headers={"X-Tracking-Token": token}).status_code == 404


def test_jeton_refuse_dans_l_url(client):
    token = creer(client)["tracking_token"]
    assert client.get(f"{TRACK}?token={token}").status_code == 422
    assert client.get(f"{TRACK}/{token}").status_code == 404


def test_suivi_sans_effet_de_bord(client):
    token = creer(client)["tracking_token"]
    for _ in range(3):
        client.get(TRACK, headers={"X-Tracking-Token": token})
    with get_sessionmaker()() as s:
        assert s.scalar(select(Order.status)) == "recue"
        assert len(s.scalars(select(Order.id)).all()) == 1


def test_reponses_jamais_en_cache(client):
    r = client.post("/v1/orders", json=commande())
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-type"] == "application/json; charset=utf-8"
    t = client.get(TRACK, headers={"X-Tracking-Token": r.json()["tracking_token"]})
    assert t.headers["cache-control"] == "no-store"


# --- T04 : limite de débit ---------------------------------------------------------------


def test_limite_de_commandes(client):
    for _ in range(5):
        creer(client)
    r = client.post("/v1/orders", json=commande())
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


def test_limite_du_suivi(client):
    for _ in range(60):
        client.get(TRACK, headers={"X-Tracking-Token": "A" * 22})
    r = client.get(TRACK, headers={"X-Tracking-Token": "A" * 22})
    assert r.status_code == 429
