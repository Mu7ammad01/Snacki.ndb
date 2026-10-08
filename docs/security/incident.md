# Procédure d'incident (J14)

À garder sous la main. Chaque cas dit **qui agit**, **quoi faire dans l'ordre** et **comment vérifier**. Responsable technique : l'admin (Mike). Côté snack : la gérante, qui prévient l'admin et peut passer la caisse en mode manuel (papier + WhatsApp) à tout moment.

## 0. Réflexes communs

1. **Noter l'heure** de début et ce qui a été vu (capture d'écran sans données de client).
2. **Ne rien effacer** : journaux Cloud Run, journal d'audit, e-mails d'alerte sont les preuves.
3. **Vérifier le projet** avant toute commande : `gcloud config get-value project` → `snacki-ndb-2026`.
4. Après l'incident : une ligne dans le journal du modèle de menaces, et un test automatique si c'était une faille.

## 1. Le site ne répond plus ou affiche des erreurs

1. Journaux : Cloud Run → `snacki-web-prod` puis `snacki-api-prod` → Journaux, filtre « Erreur ».
2. Si une mise à jour récente est en cause, **revenir à la révision précédente** (aucune reconstruction) :
   ```
   gcloud run revisions list --service snacki-api-prod --region us-central1 --project snacki-ndb-2026 --limit 3
   gcloud run services update-traffic snacki-api-prod --region us-central1 --project snacki-ndb-2026 --to-revisions <REVISION_PRECEDENTE>=100
   ```
   (même chose pour `snacki-web-prod` si besoin), puis corriger par une PR normale.
3. Vérifier : la page d'accueil affiche le menu ; une commande de test **en staging**.

## 2. Un secret a fuité (mot de passe de la base, clé Gemini, secret OAuth, clé de session)

1. **Faire tourner le secret** chez son émetteur (Neon, AI Studio, Google Cloud), sans le coller nulle part sauf dans une invite masquée :
   - clé Gemini : `GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/setup-gemini.sh prod` ;
   - autres secrets : `gcloud secrets versions add <secret> --data-file=-` puis coller dans l'invite.
2. **Désactiver l'ancienne version** : `gcloud secrets versions disable <n> --secret <secret>`.
3. **Redéployer** pour que l'API lise la nouvelle version : relancer le dernier déploiement (Actions → deploy → Re-run all jobs).
4. Clé de session changée = **tout le staff est déconnecté** : c'est voulu.
5. Vérifier : l'ancienne valeur ne fonctionne plus (connexion refusée, appel Gemini refusé).

## 3. Un compte du staff est compromis (téléphone volé, mot de passe Google divulgué)

1. Admin → **Équipe** → désactiver le compte : effet immédiat, ses sessions tombent.
2. La personne sécurise son compte Google (mot de passe, double authentification, appareils connectés).
3. Lire le journal d'audit des dernières 48 h (encaissements, annulations, fidélité) et corriger ce qui doit l'être.
4. Réactiver le compte seulement après l'étape 2.

## 4. Données perdues ou corrompues (base effacée, compte Neon compromis) — menace T24

1. **Arrêter les écritures** : la gérante passe la caisse en mode manuel ; les commandes en ligne échoueront proprement.
2. **Choisir la source** :
   - erreur de moins de 6 h : la **restauration à un instant** de Neon (historique de 6 h) suffit, directement dans la console Neon ;
   - sinon : la **sauvegarde de la nuit** (30 jours, non effaçables).
3. **Restaurer dans une base neuve** (nouvelle branche ou base Neon, vide), jamais par-dessus la production :
   ```
   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/restore-to.sh            # la plus récente
   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/restore-to.sh gs://snacki-ndb-2026-backups/prod/AAAA/MM/JJ/<fichier>.dump
   ```
   L'URL de la base neuve est demandée dans une invite masquée. Le script refuse la base de production actuelle et une base non vide, puis affiche ce qu'il a restauré.
4. **Basculer la production** vers la base restaurée, après vérification des chiffres :
   ```
   gcloud secrets versions add snacki-db-url-prod --project snacki-ndb-2026 --data-file=-   # coller l'URL, puis Ctrl-D
   ```
   puis relancer le dernier déploiement (Actions → deploy → Re-run all jobs).
5. **Ressaisir** les ventes notées sur papier depuis la dernière sauvegarde (vente au comptoir).
6. Si le compte Neon a été compromis : changer son mot de passe, activer la double authentification, faire tourner l'URL de la base (cas 2).

## 5. Le domaine snackindb.com ne pointe plus vers Snacki

1. Vérifier chez Cloudflare (DNS) que les 9 enregistrements sont intacts et en « DNS only ».
2. En attendant, l'adresse run.app de production fonctionne toujours : la communiquer à l'équipe.
3. Si le compte Cloudflare a été compromis : reprendre le compte, double authentification, puis remettre les enregistrements (`./infra/gcp/setup-domain.sh` les affiche).

## Contacts et accès à vérifier chaque mois

- Double authentification active sur : Google (admin), GitHub, Neon, Cloudflare.
- Le test de restauration du 1er du mois est vert (Actions → restore-test).
- Au moins deux comptes admin actifs dans l'app (l'admin et la gérante).
