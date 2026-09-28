# ADR 0002 · Portes de sécurité dès le premier commit

- Statut : acceptée (J1, 27/09/2026)

## Contexte

Le guide initial plaçait les scans et le pentest en semaine 3. Une faille trouvée en fin de projet coûte plus cher à corriger, et un secret commité à J2 reste dans l'historique Git pour toujours.

## Décision

Dès J1, avant toute ligne de code applicatif :

- **Sur le poste** (`pre-commit`) : gitleaks, ruff (règles de sécurité `S`), Bandit, interdiction des fichiers `.env`, interdiction de commiter sur `main`, contrôle de la liste ASVS.
- **En CI** (`.github/workflows/ci.yml`) : gitleaks sur tout l'historique, les mêmes hooks, les tests des outils.
- **Sur GitHub** : branche `main` protégée (PR et portes vertes obligatoires), protection des pushs contre les secrets, alertes et correctifs Dependabot, signalement privé des failles.
- **Chaîne d'approvisionnement** : actions épinglées par empreinte SHA, jeton CI en lecture seule, versions d'outils figées.

Les portes suivantes s'ajoutent au jour où le code qu'elles contrôlent apparaît (tests d'autorisation J3, image et SCA J5, IA J9, DAST J12).

## Conséquences

- Positif : aucune dette de sécurité accumulée ; chaque PR montre son état de sécurité.
- Négatif : premiers commits plus lents (installation de pre-commit, faux positifs à régler).
- Règle pour les faux positifs : une exception se documente dans le dépôt, avec sa raison et une date d'expiration.
