# Synthèse de sécurité · v1.0 (8 octobre 2026)

**En une phrase** : les 28 menaces du modèle STRIDE sont traitées ; l'audit (ASVS niveau 1) et le scan OWASP ZAP complet n'ont trouvé aucune faille haute ; les 5 constats faibles sont corrigés ou acceptés et documentés.

| Indicateur | Valeur |
| --- | --- |
| Menaces traitées | 28 / 28 ([modèle](threat-model.md)) |
| Portes automatiques | 9, toutes bloquantes ([README](../../README.md#sécurité)) |
| OWASP ASVS niveau 1 | 47 exigences satisfaites, 22 sans objet, 1 à mesurer chez Google (versions TLS) ([suivi](asvs-l1.md)) |
| Failles hautes ou critiques ouvertes | 0 ([audit](audit-j13.md)) |
| Scan ZAP complet de staging | 0 haute, 1 moyenne acceptée (proxy de Google), 2 faibles corrigées |
| Images déployées | Signées par la CI, SBOM attaché, vérifiées avant staging et production |
| Sauvegardes | Chaque nuit, non effaçables 30 jours, restauration testée chaque mois |
| Secrets dans le dépôt ou dans GitHub | 0 (Secret Manager, déploiement sans clé) |

## Risques résiduels acceptés

| Risque | Pourquoi accepté | Parade |
| --- | --- | --- |
| Offre gratuite Gemini : Google peut utiliser les textes envoyés | Coût nul, textes masqués (téléphones, e-mails) ou agrégats seulement | Passer à l'offre payante si le volume grandit |
| Limite de débit en mémoire (2 instances au plus) | La limite peut doubler au pire | Quota IA déjà en base |
| Image ZAP non figée (`stable`), cosign en v2.4.1 | Outils de la CI, sans secret | Revue mensuelle des versions |
| Comptes tiers (Google, GitHub, Neon, Cloudflare) | Hors de l'app | Double authentification, vérifiée chaque mois ([incident](incident.md)) |

## Vérification mensuelle (10 minutes)

1. Actions → `restore-test` vert le 1er du mois.
2. Alertes Dependabot et CodeQL : aucune ouverte depuis plus de 7 jours.
3. Double authentification active sur les 4 comptes tiers.
4. Au moins deux comptes admin actifs dans l'app.
5. Versions de cosign et de l'image ZAP revues.
