# ADR 0005 · Configuration par l'environnement et tests sur PostgreSQL

- Statut : acceptée (J2, 27/09/2026)
- Contexte : socle de l'API ; menace T05 (injection SQL) ; exigence ASVS V1.2.4.

## Contexte

L'API a besoin d'une URL de base contenant un mot de passe. Les tests doivent prouver que les requêtes résistent à l'injection et que les migrations fonctionnent sur le moteur réellement utilisé en production (Neon, donc PostgreSQL).

## Décision

1. **Configuration uniquement par variables d'environnement** (`pydantic-settings`, préfixe `SNACKI_`). L'URL de la base n'a pas de valeur par défaut ; elle est typée `SecretStr` pour ne jamais apparaître dans un affichage, un journal ou une erreur. Le fichier `.env` sert au confort local : il est ignoré par git et bloqué par pre-commit.
2. **Règles de production vérifiées au démarrage** : `sslmode=require` vers la base, origines CORS en HTTPS, documentation `/docs` désactivée. Une configuration dangereuse empêche l'API de démarrer.
3. **Tests sur un vrai PostgreSQL**, jamais SQLite : une base jetable en CI (conteneur `postgres:16`), une base locale en développement. Chaque lancement rejoue toutes les migrations Alembic depuis zéro.
4. **Migrations réversibles et vérifiées** : la CI applique `upgrade head`, vérifie qu'aucune différence ne reste entre modèles et base (`alembic check`), puis annule tout (`downgrade base`).

## Conséquences

- Positif : une erreur de configuration se voit au démarrage, pas en production ; les tests couvrent les contraintes, les énumérations et les expressions régulières propres à PostgreSQL.
- Négatif : il faut un PostgreSQL pour lancer les tests en local (documenté dans `apps/api/README.md`).
- Le mot de passe de la base CI (`ci-only-not-a-secret`) est public par nature : la base n'existe que le temps du job et n'est pas joignable depuis Internet.
