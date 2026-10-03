# API Snacki (FastAPI)

État : **J3** · menu des 9 produits, commandes côté serveur, suivi par jeton, limite de débit.

| Route | Rôle |
| --- | --- |
| `GET /healthz` | Vivacité : le processus répond (sans toucher la base) |
| `GET /readyz` | Disponibilité : la base répond |
| `GET /v1/menu?category=jus\|delices` | Menu disponible, trié, prix en MRU, noms FR et AR |
| `GET /v1/menu/{id}` | Un produit (identifiant : minuscules et tirets) |
| `POST /v1/orders` | Crée une commande : le client envoie produits et quantités, l'API calcule le total ; renvoie le numéro et le jeton de suivi (une seule fois). 5 par minute et 20 par heure. |
| `GET /v1/orders/track` | Suivi, avec le jeton dans l'en-tête `X-Tracking-Token` (jamais dans l'URL) ; aucune donnée personnelle ; 60 par minute. |
| `GET /docs` | Documentation interactive, **uniquement** en `dev` et `test` |

## Démarrer en local

Prérequis : Python 3.11+, un PostgreSQL 16 local (ou une branche Neon de développement).

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # puis mettre le vrai mot de passe local (.env est ignoré par git)
alembic upgrade head              # crée les tables et insère le menu
uvicorn snacki_api.main:app --reload --app-dir src
```

Tests (sur une base PostgreSQL dédiée, vidée puis recréée à chaque lancement) :

```bash
export SNACKI_TEST_DATABASE_URL=postgresql://snacki:MOT_DE_PASSE@localhost:5432/snacki_test
pytest --cov
```

## Configuration

Toutes les valeurs viennent de variables d'environnement préfixées `SNACKI_` (voir `.env.example`).

| Variable | Obligatoire | Règle |
| --- | --- | --- |
| `SNACKI_DATABASE_URL` | oui | Pas de valeur par défaut : sans elle, l'API refuse de démarrer. En `staging` et `prod`, `sslmode=require` est exigé. |
| `SNACKI_ENVIRONMENT` | non | `dev` (défaut), `test`, `staging`, `prod`. En `staging`/`prod`, `/docs` est désactivé. |
| `SNACKI_RETENTION_DAYS` | non | Délai avant anonymisation des coordonnées des clients : 90 jours par défaut (30 à 730). |
| `SNACKI_CORS_ORIGINS` | non | Liste JSON d'origines fixes ; en production, HTTPS uniquement. Vide par défaut : l'API est appelée par le serveur web, pas par le navigateur (ADR 0001). |

En staging et en production, ces valeurs viendront de Secret Manager (J5), jamais d'un fichier.

## Importer l'historique Excel (J8, ADR 0010)

Script d'administration, lancé depuis `apps/api` dans le Codespace. Le classeur reste hors du dépôt (`.gitignore`).

```bash
pip install -r requirements-dev.txt                 # pandas, openpyxl, defusedxml
# 1. essai à blanc sur la base locale : rapport, rien n'est écrit
PYTHONPATH=src python -m snacki_api.manage import-history ~/suivi.xlsx --dry-run
# 2. import réel en staging : l'URL de la base vient de Secret Manager, sans être affichée
SNACKI_DATABASE_URL="$(gcloud secrets versions access latest --secret=snacki-db-url-staging)" \
  PYTHONPATH=src python -m snacki_api.manage import-history ~/suivi.xlsx
```

Relancer le même fichier ne double rien : les jours qu'il contient sont remplacés.

## Organisation

```
src/snacki_api/
  config.py      configuration (pydantic-settings, secrets en SecretStr)
  db.py          connexion SQLAlchemy (pool vérifié, délai maximal de requête 10 s)
  models.py      tables (produits, commandes, staff, journal, historique)
  schemas.py     formats de réponse (champs publics uniquement)
  repository.py  requêtes du menu (ORM, paramètres liés)
  orders.py      création de commande (prix lus en base) et suivi par jeton haché
  ratelimit.py   limite de débit en mémoire (fenêtre glissante)
  caisse.py      cycle de commande, encaissement, comptoir (J7)
  pilotage.py    chiffre d'affaires, top produits, paiements (J8)
  history.py     lecture et import de l'historique Excel (J8)
  retention.py   conservation : anonymisation à 90 jours, journal 1 an (J8)
  manage.py      migrate, purge, import-history
  main.py        application, routes, en-têtes de sécurité, erreurs sans fuite
migrations/      Alembic : 0001 à 0007 (menu, commandes, staff, caisse, historique)
tests/           tests sur PostgreSQL : menu, commandes, staff, caisse, pilotage, historique, sécurité
```
