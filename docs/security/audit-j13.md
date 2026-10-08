# Audit de sécurité J13 (8 octobre 2026)

Audit en boîte blanche (relecture du code et de la configuration) et en boîte noire (OWASP ZAP sur staging uniquement). Référentiels : OWASP ASVS niveau 1, OWASP Top 10 web et LLM. Chaque contrôle validé est couvert par un test automatique de la CI : une régression bloque la fusion.

## Contrôles vérifiés

| Domaine | Contrôle | Preuve (test automatique) | Résultat |
| --- | --- | --- | --- |
| Accès | Chaque route non publique exige un rôle | `test_staff.py::test_chaque_route_non_publique_exige_un_role` | OK |
| Accès | Caissier refusé sur pilotage, équipe, fidélité gérante ; refus journalisé | `test_pilotage.py`, `test_staff.py`, E2E « sécurité » | OK |
| Sessions | Session expirée, falsifiée, sans signature, d'une autre clé : refusée | `test_staff.py::test_session_*` | OK |
| Sessions | Déconnexion, désactivation, changement de rôle : effet immédiat | `test_staff.py` (3 tests) | OK |
| Connexion | PKCE, state, nonce, jeton Google vérifié | `test_staff.py` (8 tests) | OK |
| CSRF | Toute action du staff qui modifie vérifie l'origine | `audit.test.ts` (toutes les routes, présentes et futures) | OK |
| CSRF | Toute route publique qui modifie exige du JSON | `audit.test.ts` | OK |
| Données | Prix et total fixés par le serveur ; champ inconnu refusé | `test_orders.py::test_prix_envoye_par_le_client_refuse` | OK |
| Données | Jeton de suivi : aléatoire, haché, hors URL, même réponse pour inconnu ou expiré | `test_orders.py` (6 tests) | OK |
| Injection | SQL paramétré ; valeurs dangereuses traitées comme données | `test_security.py` | OK |
| XSS | CSP à nonce, aucun `innerHTML`, aucun blocage CSP sur le parcours client | `securite.test.ts`, E2E « client » | OK |
| Débit | Commandes, suivi, connexion, fidélité, assistant, résumé limités | `test_orders.py`, `test_staff.py`, `test_loyalty.py` | OK, voir A1 |
| IA | Liste fermée, prix en base, masquage, quota, chiffres vérifiés | `test_assistant.py`, `test_forecast.py` | OK |
| Cache | Réponses sensibles en `no-store` ; service worker sans page ni API | `test_*`, `pwa.test.ts`, `audit.test.ts` | OK |
| Chaîne | Images signées et vérifiées, SBOM, Trivy, audits de dépendances | `deploy.yml` (J12) | OK |
| En-têtes | CSP, HSTS, anti-cadre, nosniff, cookies sûrs | ZAP baseline à chaque déploiement | OK |

## Constats

| # | Gravité | Constat | Correctif (J14) | Statut |
| --- | --- | --- | --- | --- |
| A1 | Faible | Les routes de la caisse ne transmettent pas l'adresse du client à l'API : les limites de débit de l'assistant, de la fidélité et du résumé sont partagées par tout le staff. | Transmettre l'adresse (comme pour les commandes) et garder la session comme clé de repli. | Corrigé : `staffFetch` transmet l'adresse du client |
| A2 | Faible | La limite de débit est en mémoire, par instance : avec 2 instances au plus, la limite réelle peut doubler. | Accepté (documenté) ; le quota IA, lui, est déjà en base. | Accepté |
| A3 | Faible | La taille des requêtes est mesurée en caractères, pas en octets : un texte arabe peut peser jusqu'à deux fois plus. | Mesurer en octets. | Corrigé : `byteLength` (UTF-8) sur toutes les routes |
| A4 | Info | L'image ZAP suit l'étiquette `stable` ; cosign est figé en v2.4.1. | Revue mensuelle des versions. | Suivi mensuel |
| A5 | Info | Le compte Cloudflare contrôle le domaine. | Double authentification sur Cloudflare (à confirmer). | À confirmer par l'admin (procédure d'incident) |
| A6 | Info | La vérification des types Python (mypy) ne tourne pas en CI. | L'ajouter en porte 2. | Corrigé : mypy dans la CI (job api) |

Aucune faille haute ou critique trouvée par la relecture. Le scan ZAP complet de staging (workflow `zap-full`) complète ce rapport : ses résultats s'ajoutent ici.

## Résultats du scan ZAP complet (staging, 8 octobre 2026)

0 alerte haute, 1 moyenne, 2 faibles, 6 informatives.

| # | Alerte ZAP | Niveau | Analyse | Statut |
| --- | --- | --- | --- | --- |
| Z1 | Proxy Disclosure | Moyen | Révèle l'équilibreur de Google (Google Front End) devant Cloud Run : infrastructure de Google, rien de propre à Snacki. | Accepté |
| Z2 | Cross-Origin-Embedder-Policy absent | Faible | Durcissement : aucune ressource tierce n'est chargée. | Corrigé : `require-corp` |
| Z3 | Cross-Origin-Resource-Policy absent | Faible | Un autre site pourrait intégrer nos fichiers. | Corrigé : `same-origin` |
| Z4 | Cache, application moderne, User-Agent (6) | Info | Réponses sensibles déjà en `no-store`. | Rien à faire |

Le robot de ZAP parcourt mal une application rendue en JavaScript (5 adresses trouvées) : la profondeur est couverte par les tests de bout en bout et les tests d'autorisation de la CI.
