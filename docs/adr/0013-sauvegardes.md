# ADR 0013 · Sauvegarde nocturne de la base

- Statut : accepté (5 octobre 2026, avancé depuis J14)
- Contexte : la base de production est chez Neon, offre gratuite. Son historique ne permet de revenir que **6 heures** en arrière (1 Go au plus). Une erreur, une donnée abîmée par une mise à jour ou un compte détourné, découverts le lendemain, seraient irréparables. Toutes les données sont chez un seul fournisseur.

## Décision

1. Chaque nuit à **3 h (heure de Nouadhibou)**, Cloud Scheduler lance la tâche Cloud Run `snacki-backup-prod` : `python -m snacki_api.manage backup` (`backup.py`).
2. `pg_dump --format=custom` (compressé, restaurable table par table), contrôle de version client / serveur, fichier non vide, puis envoi dans `gs://<projet>-backups/prod/AAAA/MM/JJ/…dump`, sans écrasement (`ifGenerationMatch=0`).
3. **Moindre privilège** :
   - `snacki-backup-prod` lit le seul secret `snacki-db-url-prod` et peut **créer** des objets dans le bucket, ni les lire ni les effacer ;
   - la tâche ne reçoit ni le secret OAuth ni la clé des sessions (elle ne lit pas `Settings`) ;
   - `snacki-scheduler` peut seulement lancer cette tâche.
4. **Bucket** privé (accès public bloqué, accès uniforme), chiffré par Google, **conservation 30 jours** : aucune copie ne peut être effacée avant, même par un compte compromis ; effacement automatique à 31 jours.
5. **Alerte** par e-mail (Cloud Monitoring) dès qu'une exécution échoue.
6. **Test de restauration mensuel** : `infra/gcp/restore-test.sh` restaure la dernière copie dans un PostgreSQL jetable et compte les lignes. Automatisé (7 octobre 2026) : `.github/workflows/restore-test.yml`, le 1er de chaque mois et à la demande ; échec si la copie a plus de 26 h, si `pg_restore` signale une erreur ou si le menu, le staff ou le schéma manquent ; e-mail de GitHub en cas d'échec. Accès : compte `snacki-restore-test` (lecture du bucket seulement), pool d'identité `github-restore` distinct de celui du déploiement, limité à ce workflow sur main (`infra/gcp/setup-restore-ci.sh`). Les journaux n'affichent que des contrôles oui/non, aucun chiffre. Contrepartie acceptée : la copie transite quelques minutes par une machine GitHub éphémère, détruite après le job.
7. `pg_dump` et `psql` sont ajoutés à l'image de l'API (`postgresql-client-18` du dépôt officiel PostgreSQL : sa version majeure doit être au moins celle du serveur Neon, PostgreSQL 18) : une seule image, analysée par Trivy, déployée partout. La tâche est créée par `setup-backup.sh`, puis chaque déploiement lui donne la nouvelle image.

## Conséquences

- Perte maximale : les données d'une journée (point de reprise 24 h), au lieu de tout ce qui dépasse 6 heures.
- Données personnelles : une coordonnée anonymisée à 90 jours peut encore exister 30 jours dans les copies. C'est la limite écrite dans l'inventaire des données.
- Coût : quelques Mo par jour, dans la gratuité de Cloud Storage (5 Go en us-central1) et de Cloud Scheduler (3 tâches).
- Restauration réelle (incident) : procédure dans `apps/api/README.md`, toujours vers une **nouvelle branche Neon**, jamais par-dessus la base en service.
