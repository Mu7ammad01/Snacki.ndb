# Snacki

[![ci](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/ci.yml/badge.svg)](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/ci.yml)
[![codeql](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/codeql.yml/badge.svg)](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/codeql.yml)
[![deploy](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/deploy.yml/badge.svg)](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/deploy.yml)
[![restore-test](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/restore-test.yml/badge.svg)](https://github.com/Mu7ammad01/Snacki.ndb/actions/workflows/restore-test.yml)

Application en production pour **Snacki**, un snack de jus et de desserts à Nouadhibou (Mauritanie) : **[snackindb.com](https://snackindb.com)**.

- **Clients** : menu en français ou en arabe (langue du téléphone), commande à emporter ou en livraison, suivi en direct, carte de fidélité à QR. Installable sur le téléphone.
- **Caisse** : commandes en temps réel avec son et notification, vente au comptoir, encaissement (espèces ou wallet), fidélité, assistant IA qui transforme un message WhatsApp en vente.
- **Gérante** : chiffre d'affaires, produits les plus vendus, prévisions sur 7 jours, résumé du jour, historique Excel importé.

> **Version 1.0** · 15 jours de construction (J1 à J15), chaque jour testé, scanné, déployé en staging puis en production. Les 28 menaces du modèle de sécurité sont traitées. Historique : [CHANGELOG](CHANGELOG.md).

## Architecture

```mermaid
flowchart LR
  C[Client] -- HTTPS --> W[web · Next.js]
  S[Staff] -- HTTPS --> W
  D[Cloudflare · DNS seul] -. snackindb.com .-> W
  W -- "jeton d'identité Google" --> A[api · FastAPI, privée]
  A -- SQL paramétré --> DB[(PostgreSQL · Neon)]
  A --> G[Google OAuth 2.0]
  A -- textes masqués --> L[API Gemini]
  B[Sauvegarde 3 h] --> GCS[(Cloud Storage · 30 jours)]
```

| Brique | Technologie |
| --- | --- |
| Front | TypeScript, Next.js 16, React 19, PWA FR/AR |
| API | Python, FastAPI, Pydantic |
| Données | PostgreSQL (Neon), SQLAlchemy, Alembic |
| IA | Gemini (assistant de commande, résumé vérifié), prévisions en Python |
| Identité | OAuth 2.0 Google avec PKCE, sessions signées, rôles |
| Hébergement | Docker, Google Cloud Run ; domaine et DNS chez Cloudflare |
| CI/CD | GitHub Actions, déploiement sans clé (Workload Identity Federation) |

## Sécurité

Démarche **DevSecOps** : la sécurité est un contrôle automatique du pipeline, comme les tests. Rien n'atteint la production sans 9 portes vertes, une image signée par la CI et une approbation humaine.

| Porte | Outils |
| --- | --- |
| 1 · Secrets | gitleaks (poste + CI), protection des pushs GitHub |
| 2 · Qualité | ruff, Bandit, mypy, hooks pre-commit |
| 3 · Tests | pytest sur PostgreSQL (couverture ≥ 80 %), Vitest, Playwright de bout en bout |
| 4 · Autorisations | tests des rôles, des sessions et des liens de suivi (anti-BOLA) |
| 5 · Analyse du code | CodeQL (Python, TypeScript) |
| 6 · Dépendances | pip-audit, npm audit, Dependabot |
| 7 · Images | non root, Trivy, SBOM CycloneDX, signature cosign vérifiée avant chaque déploiement |
| 8 · IA | jeu d'évaluation de l'assistant ; chiffres de l'IA vérifiés ; quota quotidien |
| 9 · Application en ligne | OWASP ZAP sur staging à chaque déploiement |

- [Synthèse de sécurité v1.0](docs/security/README.md)
- [Modèle de menaces (STRIDE, 28 menaces, toutes traitées)](docs/security/threat-model.md)
- [Audit J13 et scan ZAP complet](docs/security/audit-j13.md)
- [Procédure d'incident](docs/security/incident.md)
- [Suivi OWASP ASVS 5.0 niveau 1](docs/security/asvs-l1.md)
- [Décisions d'architecture (17 ADR)](docs/adr/)
- [Politique de sécurité](SECURITY.md)

## Démarrer

Prérequis : Python 3.11+, Git, Graphviz (pour régénérer le schéma de flux).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install            # active les portes locales à chaque commit
pre-commit run --all-files    # vérifie tout le dépôt
pytest                        # tests des outils de sécurité
```

Travailler toujours sur une branche (`git switch -c j2-socle-api`) : `main` n'accepte que des pull requests.

## Déployer

Chaque fusion sur `main` déclenche `.github/workflows/deploy.yml` après une CI verte : images construites et analysées une fois, publiées dans Artifact Registry, déployées en **staging**, puis en **production** après approbation dans GitHub ([ADR 0007](docs/adr/0007-deploiement-cloud-run.md)). Aucune clé Google n'est stockée : GitHub s'authentifie par Workload Identity Federation.

| Service | Accès |
| --- | --- |
| `snacki-web-staging`, `snacki-web-prod` | public (HTTPS) |
| `snacki-api-staging`, `snacki-api-prod` | privé : seul le serveur web du même environnement peut l'appeler |

Mise en place, une seule fois : `./infra/gcp/setup-deploy.sh <projet> <propriétaire/dépôt>`, puis `./infra/gcp/setup-auth.sh` pour la connexion du staff ([ADR 0008](docs/adr/0008-connexion-du-staff.md)). Domaine : `setup-domain.sh` ; sauvegardes : `setup-backup.sh` et `setup-restore-ci.sh` ; assistant IA : `setup-gemini.sh`.

## Organisation du dépôt

```
apps/api/        API FastAPI (voir apps/api/README.md)
apps/web/        PWA Next.js (voir apps/web/README.md)
docs/security/   modèle de menaces (as code + texte), ASVS, schéma de flux
docs/adr/        décisions d'architecture
infra/github/    réglages de sécurité du dépôt (branche protégée, alertes)
infra/gcp/       projet Google Cloud, budget, déploiement (comptes, secrets, Cloud Run)
scripts/         outils Python : vérification du dépôt, ASVS, schéma de flux
tests/           tests des outils
```

## Licence

MIT, voir [LICENSE](LICENSE). Le texte de l'OWASP ASVS dans `docs/security/asvs/` reste sous CC BY-SA 4.0.
