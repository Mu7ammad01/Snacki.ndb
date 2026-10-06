"""J10 : prévisions, résumé du jour, vérification des chiffres de l'IA (T16), quota (T15)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from snacki_api import auth, forecast, quota, resume
from snacki_api.db import get_sessionmaker
from snacki_api.models import HistoryItem, HistorySale, StaffRole, StaffUser

SECRET = "k" * 48
TODAY = datetime.now(UTC).date()


@pytest.fixture(autouse=True)
def base_vide():
    resume._cache.clear()
    with get_sessionmaker()() as s:
        s.execute(
            text(
                "TRUNCATE ai_usage, history_item, history_sale, audit_log, staff_user, "
                "order_line, orders RESTART IDENTITY CASCADE"
            )
        )
        s.commit()


def make_api(settings, key: str | None = None, **extra) -> TestClient:
    from snacki_api.main import create_app

    configured = settings.model_copy(
        update={
            "oauth_client_id": "client-test",
            "oauth_client_secret": SecretStr("secret-de-test"),
            "oauth_redirect_uri": "https://web.test/auth/callback",
            "session_secret": SecretStr(SECRET),
            "gemini_api_key": SecretStr(key) if key else None,
            **extra,
        }
    )
    return TestClient(create_app(configured))


def membre(role: StaffRole) -> dict[str, str]:
    with get_sessionmaker()() as s:
        user = StaffUser(email=f"{role.value}@gmail.com", role=role)
        s.add(user)
        s.commit()
        return {"X-Staff-Session": auth.new_session(SECRET, user.id, user.session_version, 8)}


def historique(day: date, items, ref: str = "cmd1") -> None:
    with get_sessionmaker()() as s:
        s.add(
            HistorySale(
                service_day=day,
                ref=ref,
                raw_text="x",
                total_mru=100,
                batch="test",
                items=[HistoryItem(product_id=p, label=p, quantity=q) for p, q in items],
            )
        )
        s.commit()


# --- Modèle (sans base) ----------------------------------------------------------------------


def serie(days: dict[date, int]) -> tuple[dict, set]:
    return {d: {"avocat": q} for d, q in days.items()}, set(days)


def test_meme_jour_de_semaine_pondere():
    t = date(2026, 10, 6)
    s, open_days = serie(
        {t - timedelta(weeks=1): 10, t - timedelta(weeks=2): 20, t - timedelta(days=1): 99}
    )
    # (10×4 + 20×3) / 7 : la semaine la plus récente pèse plus ; la veille n'entre pas.
    assert forecast.predict(s, open_days, t) == {"avocat": pytest.approx(100 / 7)}


def test_repli_sur_les_derniers_jours_et_rien_sans_donnees():
    t = date(2026, 10, 6)
    s, open_days = serie({t - timedelta(days=1): 4, t - timedelta(days=2): 6})
    assert forecast.predict(s, open_days, t) == {"avocat": 5}
    assert forecast.predict({}, set(), t) == {}


def test_jour_ferme_ignore():
    t = date(2026, 10, 6)
    s, open_days = serie({t - timedelta(weeks=1): 10, t - timedelta(weeks=3): 10})
    assert forecast.predict(s, open_days, t) == {"avocat": pytest.approx(10)}


def test_backtest_bat_la_methode_naive_sur_un_rythme_stable():
    today = date(2026, 10, 6)
    days = {}
    for k in range(1, 70):
        d = today - timedelta(days=k)
        base = 20 if d.weekday() == 4 else 8  # le vendredi est plus fort
        days[d] = base + (3 if k % 2 else -3)  # bruit alterné
    s, open_days = serie(days)
    check = forecast.backtest(s, open_days, today)
    assert check["days"] == 28 and check["model_error"] <= check["naive_error"]
    assert forecast.reliability(len(open_days), check) == "bonne"
    assert forecast.reliability(5, check) == "insuffisante"


# --- Vérification des chiffres de l'IA (T16) ------------------------------------------------

FACTS = {
    "jour": "2026-10-06",
    "jour_semaine": "mardi",
    "chiffre_affaires_mru": 4250,
    "commandes": 18,
    "panier_moyen_mru": 236,
    "meme_jour_semaine_derniere_mru": 3800,
    "evolution_pct": 12,
    "meilleures_ventes": [{"produit": "Avocat", "quantite": 9}],
    "paiement_principal": {"moyen": "espèces", "montant_mru": 3100},
    "commandes_offertes": 2,
    "annulees_ou_refusees": 0,
    "demain": {"jour_semaine": "mercredi", "articles_prevus": 20, "principaux": []},
}


def test_texte_modele():
    t = resume.template(FACTS)
    assert t.startswith("Mardi 06/10 : 4 250 MRU sur 18 commandes (panier moyen 236 MRU).")
    assert "+12 % par rapport à mardi dernier (3 800 MRU)" in t and "Avocat (9)" in t
    assert resume.verify(t, FACTS)


@pytest.mark.parametrize(
    "texte,ok",
    [
        ("Belle journée ce mardi 06/10 : 4 250 MRU pour 18 commandes, +12 %.", True),
        ("Mardi : 4250 MRU, Avocat en tête avec 9 ventes.", True),
        ("Mardi : 4 300 MRU sur 18 commandes.", False),  # chiffre inventé
        ("Mardi : 4 250 MRU, soit 236,1 MRU par commande.", False),  # décimal recalculé
        ("Mardi : 4 250 MRU, deux fois plus qu'un lundi.", False),  # nombre en lettres
        ("Mardi : 4 250 MRU, presque le double de lundi.", False),
        ("", False),
        ("x" * 701, False),
    ],
)
def test_verification_des_chiffres(texte, ok):
    assert resume.verify(texte, FACTS) is ok


def test_reformulation_ecartee_si_chiffre_invente(monkeypatch):
    monkeypatch.setattr(resume, "_gemini", lambda *a: "Mardi : 9 999 MRU, record battu !")
    text, engine, warnings = resume.rephrase(FACTS, "cle", "modele-test")
    assert engine == "modele" and text == resume.template(FACTS) and warnings
    assert resume.cached(FACTS) is None


def test_reformulation_acceptee_et_mise_en_cache(monkeypatch):
    monkeypatch.setattr(resume, "_gemini", lambda *a: "Mardi, 4 250 MRU sur 18 commandes.")
    assert resume.rephrase(FACTS, "cle", "m")[1] == "gemini"
    assert resume.cached(FACTS) == "Mardi, 4 250 MRU sur 18 commandes."


# --- Quota quotidien (T15) ------------------------------------------------------------------


def test_quota_plafonne_et_repart_le_lendemain():
    with get_sessionmaker()() as s:
        assert [quota.take(s, "resume", 2, TODAY) for _ in range(3)] == [True, True, False]
        assert quota.take(s, "resume", 2, TODAY + timedelta(days=1))
        assert not quota.take(s, "assistant", 0, TODAY)
        s.commit()
        assert quota.used(s, "resume", TODAY) == 2


# --- Routes ---------------------------------------------------------------------------------


def test_previsions_reservees_a_la_gerante(settings):
    api = make_api(settings)
    assert api.get("/v1/pilotage/previsions").status_code == 401
    assert api.get("/v1/pilotage/previsions", headers=membre(StaffRole.CAISSIER)).status_code == 403


def test_previsions_depuis_l_historique(settings):
    api = make_api(settings)
    for k in range(1, 5):
        historique(TODAY - timedelta(weeks=k), [("avocat", 8), ("crepe", 2)], ref=f"a{k}")
        historique(TODAY - timedelta(weeks=k, days=1), [("salade", 3)], ref=f"b{k}")
    r = api.get("/v1/pilotage/previsions", headers=membre(StaffRole.GERANTE))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    d = r.json()
    assert d["reliability"] == "insuffisante" and d["open_days"] == 8 and len(d["days"]) == 7
    day0 = d["days"][0]
    assert day0["day"] == TODAY.isoformat() and day0["units"] == 10
    assert [i["product_id"] for i in day0["items"]] == ["avocat", "crepe"]
    with get_sessionmaker()() as s:
        prix = dict(s.execute(text("SELECT id, price_mru FROM product")).all())
    assert day0["revenue_mru"] == 8 * prix["avocat"] + 2 * prix["crepe"]


def test_resume_modele_sans_cle_et_ia_verifiee(settings, monkeypatch):
    h = membre(StaffRole.GERANTE)
    historique(TODAY, [("avocat", 2)])
    r = make_api(settings).get("/v1/pilotage/resume", params={"ia": True}, headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["engine"] == "modele" and not d["ai_available"] and "aucune vente" not in d["text"]

    monkeypatch.setattr(resume, "_gemini", lambda *a: "Journée calme : 100 MRU.")
    api = make_api(settings, key="cle-de-test-assez-longue", ai_cap_resume=1)
    d = api.get("/v1/pilotage/resume", params={"ia": True}, headers=h).json()
    assert d["engine"] == "gemini" and d["text"] == "Journée calme : 100 MRU."
    resume._cache.clear()
    d = api.get("/v1/pilotage/resume", params={"ia": True}, headers=h).json()
    assert d["engine"] == "modele" and "Quota" in d["warnings"][0]


def test_resume_jour_futur_refuse(settings):
    api = make_api(settings)
    r = api.get(
        "/v1/pilotage/resume",
        params={"day": (TODAY + timedelta(days=1)).isoformat()},
        headers=membre(StaffRole.GERANTE),
    )
    assert r.status_code == 422


def test_assistant_bascule_en_local_quand_le_quota_est_atteint(settings, monkeypatch):
    from snacki_api import assistant

    def interdit(*a, **k):
        raise AssertionError("Gemini ne doit pas être appelé au-delà du quota")

    monkeypatch.setattr(assistant, "parse_gemini", interdit)
    api = make_api(settings, key="cle-de-test-assez-longue", ai_cap_assistant=0)
    r = api.post(
        "/v1/caisse/assistant", json={"text": "2 crepes"}, headers=membre(StaffRole.CAISSIER)
    )
    assert r.status_code == 200
    d = r.json()
    assert d["engine"] == "local" and d["lines"][0]["quantity"] == 2
    assert any("Quota" in w for w in d["warnings"])
