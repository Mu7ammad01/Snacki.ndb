# ADR 0007 · Déploiement sur Cloud Run : sans clé, API privée, staging puis production

Date : 2 octobre 2026 · Statut : accepté

## Contexte

À J5, Snacki passe du Codespace à Internet. Il faut déployer automatiquement depuis GitHub sans stocker de clé Google (T21), séparer staging et production jusqu'aux secrets (T22), rendre l'API injoignable depuis Internet (ADR 0001) et rester dans l'offre gratuite (T23).

## Décisions

1. **Workload Identity Federation** : GitHub signe un jeton OIDC pour chaque job ; Google l'échange contre un accès de quelques minutes au compte `snacki-deployer`. Condition côté Google : identifiant numérique du dépôt, branche `main` et workflow `deploy.yml` uniquement. Aucune clé n'existe, donc aucune ne peut fuir.
2. **Moindre privilège** : 5 comptes de service, aucun avec un rôle large. Le déployeur peut déployer et publier des images, et « agir en tant que » les 4 comptes d'exécution, rien d'autre (il ne lit aucun secret). Chaque API ne lit que le secret de son environnement. Le compte par défaut de Cloud Run (rôle Éditeur sur tout le projet) n'est jamais utilisé.
3. **API privée** : `snacki-api-*` refuse toute requête sans jeton d'identité Google ; seul `snacki-web-<même environnement>` a le rôle `run.invoker`. Le serveur web obtient ce jeton auprès du serveur de métadonnées (`SNACKI_API_AUTH=gcp`), l'audience étant l'adresse de l'API. Un contrôle de fumée vérifie à chaque déploiement que l'API répond 403 sans jeton.
4. **Les droits sont posés une fois** par `infra/gcp/setup-deploy.sh` (services créés avec une image d'attente). Le workflow ne fait que changer d'image : le déployeur n'a pas le droit de modifier l'IAM, donc ne peut pas rendre l'API publique.
5. **Une image, deux environnements** : construite et analysée (Trivy) une seule fois, désignée par son empreinte `sha256`, déployée en staging puis, après approbation dans GitHub, en production.
6. **Migrations par Cloud Run Job** avant chaque nouvelle version de l'API (`alembic upgrade head`), avec le compte et le secret de l'environnement.
7. **Neon : une branche par environnement** (`staging` créée depuis `main`), connexion directe (sans pooler) en `sslmode=require`.
8. **Garde-fous de coût** : 0 instance au repos, 2 au maximum ; registre nettoyé (3 versions gardées par image) ; journaux gardés 30 jours.

## Conséquences

- `X-Forwarded-For` : le web garde le dernier élément (ajouté par le frontal de Google) ; l'API, privée, garde le premier (posé par le web) avec `SNACKI_TRUST_FORWARDED_FOR=true`. Vérifié en ligne par un test de limite de débit depuis deux adresses.
- La limite de débit est en mémoire : avec 2 instances, un client peut obtenir jusqu'au double. Accepté pour J5, revu si les abus apparaissent (T04).
- Risque résiduel : un code fusionné sur `main` peut déployer en staging sans approbation. Couvert par la protection de `main` (PR et 8 portes) ; la production exige en plus l'approbation.
- La base de production est la branche `main` de Neon utilisée depuis J2 : les commandes de test devront être purgées avant l'ouverture (J15).
- Plus tard : un rôle PostgreSQL sans droit de modifier le schéma pour l'API, distinct de celui des migrations (J14).
