# ADR 0001 · Monorepo et stack en 7 briques

- Statut : acceptée (J1, 27/09/2026)
- Contexte : plan v3, 150 h, 0 €, technologies les plus demandées, back-end en Python.

## Contexte

Snacki a deux applications (web et api) qui évoluent ensemble : un changement de schéma d'API touche presque toujours le front. Un seul développeur les maintient.

## Décision

1. **Un seul dépôt** (`apps/web`, `apps/api`, `infra/`, `docs/`) : une PR contient le changement complet, la CI voit tout, un seul endroit à protéger.
2. **Stack** : Next.js + Tailwind (web), FastAPI + Pydantic (api), PostgreSQL Neon + SQLAlchemy + Alembic, scikit-learn + Gemini, OAuth Google (Authlib) + JWT, Docker + Cloud Run, GitHub Actions.
3. **L'API n'est pas exposée à Internet** : le navigateur parle à web, web parle à l'API avec une identité de service (rôle IAM `run.invoker`). À confirmer à J5 : le suivi en direct doit traverser web en flux continu.

## Conséquences

- Positif : une seule CI, des portes appliquées partout, moins de surface d'attaque (une seule entrée publique).
- Négatif : web devient un point de passage obligé ; s'il tombe, tout tombe. Accepté à l'échelle de Snacki.
- À surveiller : le temps de construction de la CI, qui grandit avec les deux applications (filtres par chemin à J5).
