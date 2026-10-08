# Historique des versions

Chaque jour du plan est un tag Git (`j1` … `j14`), déployé en staging puis en production après approbation.

## v1.0 · 8 octobre 2026

Première version complète. 28 menaces sur 28 traitées, 9 portes de sécurité actives.

| Tag | Livré |
| --- | --- |
| j1 | Dépôt, projet Google Cloud, modèle de menaces STRIDE, hooks pre-commit |
| j2 | API FastAPI, base PostgreSQL, migrations, menu |
| j3 | Commande en ligne, total recalculé par le serveur, lien de suivi |
| j4 | Application client FR/AR, CSP à nonce |
| j5 | Déploiement automatique sur Cloud Run (staging, production), sans clé |
| j6 | Connexion du staff avec Google, rôles, sessions révocables |
| j7 | Caisse : accepter, préparer, encaisser, vente au comptoir, journal d'audit |
| j8 | Pilotage et import de l'historique Excel |
| j8b | Cartes de fidélité à QR |
| j8t, j8q | Domaine snackindb.com, sauvegarde nocturne |
| j9 | Assistant IA : message WhatsApp → vente proposée |
| j10 | Prévisions sur 7 jours, résumé du jour vérifié, quota IA |
| j11 | Tests de bout en bout, application installable, test de restauration mensuel |
| j12 | SBOM, images signées et vérifiées, OWASP ZAP |
| j13 | Audit de sécurité et scan ZAP complet |
| j14 | Correctifs de l'audit, restauration réelle outillée, procédure d'incident |
| lot-a | Réunion 5 : langue du téléphone, Espèces ou Wallet, notification détaillée, bouton WhatsApp, grands écrans |

## Prochaines versions

- **v1.1** : nouveau pilotage avec graphiques, rapport Excel et PDF, page Historique filtrable.
- **v1.2** : gestion du menu, stock par ingrédient, carte de fidélité créée à la première commande.
