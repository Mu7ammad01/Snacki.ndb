# ADR 0008 · Connexion du staff : Google OAuth géré par l'API, derrière le serveur web

Date : 5 octobre 2026 · Statut : accepté

## Contexte

À J6, la gérante, le caissier et l'admin doivent se connecter pour accéder à la caisse (J7), au pilotage (J8) et à la gestion de l'équipe. L'API est privée (ADR 0007) : le navigateur ne peut pas l'atteindre. Le plan v3 prévoit OAuth 2.0 Google et des rôles vérifiés côté serveur. Menaces visées : T07 à T10 et T12.

## Décisions

1. **Aucun mot de passe Snacki** : connexion avec Google (OpenID Connect, code d'autorisation + PKCE S256, `state`, `nonce`). Google gère les mots de passe et la double authentification.
2. **L'API décide, le web relaie** (« backend for frontend ») : l'API tire `state`, `nonce` et le vérificateur PKCE, échange le code avec le secret du client, vérifie le jeton d'identité (RS256, clés publiées par Google, `aud`, `iss`, `exp`, `nonce`, e-mail vérifié) et signe la session. Le web ne fait que ranger les jetons dans des cookies et appeler l'API.
3. **Liste blanche** : seules les adresses de la table `staff_user` peuvent se connecter. Le premier admin est créé par le job de migration (`SNACKI_BOOTSTRAP_ADMIN_EMAIL`), une seule fois ; les autres par l'admin, depuis l'écran « Équipe ». Le client OAuth reste en mode « test » chez Google : seuls les utilisateurs de test déclarés peuvent se connecter (deuxième liste blanche).
4. **Session = JWT HS256 signé par l'API**, 8 h, contenant l'identifiant du membre et une **version de session**, sans le rôle. À chaque requête, l'API relit le compte : inactif, version différente ou rôle insuffisant ⇒ refus. Déconnexion, changement de rôle et désactivation augmentent la version : toutes les sessions du compte tombent aussitôt (T12).
5. **Cookies `__Host-`**, HttpOnly, Secure, SameSite=Lax, Path=/ (session 8 h, parcours OAuth 10 min). Lax plutôt que Strict, sinon la session ne serait pas envoyée juste après le retour de Google.
6. **CSRF** (T08) : SameSite=Lax et vérification de l'en-tête `Origin` sur chaque requête du staff qui modifie (comparée à `SNACKI_PUBLIC_URL`, jamais à l'en-tête Host). Le `state` protège la connexion elle-même.
7. **Contrôle d'accès dans l'API uniquement** : `require_role()` sur chaque route du staff ; un test échoue si une route non publique n'en a pas. Un refus de rôle est inscrit au journal d'audit.
8. **Un client OAuth et une clé de session par environnement**, dans Secret Manager, lisibles par la seule API de l'environnement (T22). La clé de session est tirée au hasard par `setup-auth.sh` et n'est vue par personne.

## Conséquences

- L'adresse de retour OAuth est l'adresse `status.url` du web de chaque environnement ; elle doit être déclarée dans la console Google.
- Un membre déconnecté sur un appareil l'est sur tous (version de session par compte) : simple et sûr, au prix d'un peu de confort.
- La connexion du staff ne peut pas être testée en local sans client OAuth : elle est testée par pytest (Google simulé avec de vraies signatures RSA) puis en staging.
- Plus tard (J7) : encaissements et annulations rejoignent le journal d'audit (T11).
