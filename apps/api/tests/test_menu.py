"""Le menu servi par l'API est celui du snack : 9 produits, prix en MRU, FR et AR."""

from sqlalchemy import update

from snacki_api.db import get_sessionmaker
from snacki_api.models import Product


def test_menu_complet_dans_l_ordre(client):
    r = client.get("/v1/menu")
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "MRU"
    ids = [p["id"] for p in body["products"]]
    assert ids == [
        "salade", "crepe", "avocat", "fraise", "mangue",
        "orange", "cocktail", "banane-fraise", "mojito",
    ]  # fmt: skip


def test_prix_du_menu_en_mru(client):
    prices = {p["id"]: p["price_mru"] for p in client.get("/v1/menu").json()["products"]}
    assert prices["crepe"] == 120
    assert all(v == 100 for k, v in prices.items() if k != "crepe")


def test_noms_arabes_intacts(client):
    salade = client.get("/v1/menu/salade").json()
    assert salade["name_ar"] == "صلاد فروي"
    assert salade["badge"] == "top"


def test_filtre_par_categorie(client):
    r = client.get("/v1/menu", params={"category": "delices"})
    assert [p["id"] for p in r.json()["products"]] == ["salade", "crepe"]


def test_produit_indisponible_masque(client):
    with get_sessionmaker()() as s:
        s.execute(update(Product).where(Product.id == "mojito").values(available=False))
        s.commit()
    try:
        assert "mojito" not in [p["id"] for p in client.get("/v1/menu").json()["products"]]
        assert client.get("/v1/menu/mojito").status_code == 404
    finally:
        with get_sessionmaker()() as s:
            s.execute(update(Product).where(Product.id == "mojito").values(available=True))
            s.commit()


def test_reponse_limitee_aux_champs_publics(client):
    # Les champs internes (disponibilité, ordre, date de mise à jour) ne sortent pas (ASVS V15.3.1).
    produit = client.get("/v1/menu/crepe").json()
    assert set(produit) == {
        "id", "category", "name_fr", "name_ar", "description_fr",
        "description_ar", "price_mru", "badge", "photo",
    }  # fmt: skip


def test_produit_inconnu(client):
    assert client.get("/v1/menu/pizza").status_code == 404


def test_la_base_refuse_un_prix_aberrant():
    import pytest
    from sqlalchemy.exc import IntegrityError

    with get_sessionmaker()() as s, pytest.raises(IntegrityError):
        s.execute(update(Product).where(Product.id == "crepe").values(price_mru=-5))
        s.flush()
