# OWASP ASVS 5.0 niveau 1 : suivi pour Snacki

Fichier généré par `scripts/asvs_checklist.py` à partir de `docs/security/asvs/mapping-l1.json` : ne pas modifier à la main.

**70 exigences** : 44 fait · 3 prévu · 1 à vérifier · 22 N/A.

Texte des exigences : OWASP ASVS 5.0.0 (CC BY-SA 4.0), en anglais comme l'original.


## V1 · Encoding and Sanitization

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V1.2.1 | Verify that output encoding for an HTTP response, HTML document, or XML document is relevant for the context required, such as encoding the relevant … | fait | J4 | React n'insère que du texte (échappement automatique) ; aucun dangerouslySetInnerHTML, innerHTML, document.write ni eval dans le front, vérifié par un test qui parcourt les sources ; CSP à nonce. Preuve : `apps/web/tests/securite.test.ts (T06 · XSS)`. |
| V1.2.2 | Verify that when dynamically building URLs, untrusted data is encoded according to its context (e.g., URL encoding or base64url encoding for query or path … | fait | J4 | Lien wa.me construit avec encodeURIComponent ; le message de contact ne reprend que le numéro de commande s'il respecte le motif SNK-AAAA-NNN ; liens tel: construits seulement pour un numéro mauritanien valide ; jeton de suivi validé avant d'entrer dans l'URL du fragment. Preuve : `apps/web/src/lib/whatsapp.ts, apps/web/src/lib/caisse.ts, apps/web/tests/commande.test.ts, apps/web/tests/caisse.test.ts`. |
| V1.2.3 | Verify that output encoding or escaping is used when dynamically building JavaScript content (including JSON), to avoid changing the message or document … | fait | J3 | JSON produit uniquement par Pydantic/FastAPI (sérialisation sûre), jamais par concaténation de chaînes. Preuve : `apps/api/src/snacki_api/schemas.py, main.py (Utf8JSONResponse)`. |
| V1.2.4 | Verify that data selection or database queries (e.g., SQL, HQL, NoSQL, Cypher) use parameterized queries, ORMs, entity frameworks, or are otherwise protected … | fait | J2 | SQLAlchemy 2 (select, paramètres liés) pour toute requête ; entrées en liste blanche (Enum, motif d'identifiant) ; ruff S608 et Bandit B608 bloquants. Semgrep s'ajoute à J5. Preuve : `apps/api/src/snacki_api/repository.py, apps/api/tests/test_security.py (7 tests d’injection)`. |
| V1.2.5 | Verify that the application protects against OS command injection and that operating system calls use parameterized OS queries or use contextual command line … | fait | J1 | Aucun appel shell dans l'application ; ruff S602/S605 et Bandit B602/B605 bloquants en pre-commit et en CI. Preuve : `.pre-commit-config.yaml, pyproject.toml [tool.ruff.lint]`. |
| V1.3.1 | Verify that all untrusted HTML input from WYSIWYG editors or similar is sanitized using a well-known and secure HTML sanitization library or framework feature. | N/A |  | Aucun éditeur de texte riche ni saisie HTML dans Snacki. |
| V1.3.2 | Verify that the application avoids the use of eval() or other dynamic code execution features such as Spring Expression Language (SpEL). Where there is no … | fait | J1 | eval/exec interdits : ruff S307 et Bandit B307 bloquants ; ESLint no-eval côté front (J4). Preuve : `pyproject.toml [tool.ruff.lint] select S`. |
| V1.5.1 | Verify that the application configures XML parsers to use a restrictive configuration and that unsafe features such as resolving external entities are … | prévu | J8 | Import de l'historique Excel (XML) : defusedxml installé pour openpyxl, import en script d'administration et non en téléversement web. |

## V2 · Validation and Business Logic

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V2.1.1 | Verify that the application's documentation defines input validation rules for how to check the validity of data items against an expected structure. This … | fait | J3 | Règles de validation documentées par les schémas Pydantic (OrderIn, OrderItemIn), exportés dans la documentation OpenAPI (/docs en dev). Preuve : `apps/api/src/snacki_api/schemas.py`. |
| V2.2.1 | Verify that input is validated to enforce business or functional expectations for that input. This should either use positive validation against an allow list … | fait | J3 | Validation positive : produits du menu (identifiant en liste blanche, disponibilité en base), quantités 1 à 20, 1 à 10 lignes sans doublon, téléphone mauritanien à 8 chiffres (2, 3 ou 4), prénom 1 à 40 caractères sans caractère de contrôle, repère obligatoire en livraison. Preuve : `apps/api/src/snacki_api/schemas.py, apps/api/tests/test_orders.py (tests de lignes, téléphone, prénom, repère)`. |
| V2.2.2 | Verify that the application is designed to enforce input validation at a trusted service layer. While client-side validation improves usability and should be … | fait | J3 | Toute validation refaite dans l'API ; la validation du front n'est qu'une aide à la saisie. Champs inconnus refusés (extra=forbid) : un prix ou un total envoyé par le client rend la requête invalide. Preuve : `apps/api/tests/test_orders.py : test_prix_envoye_par_le_client_refuse, test_total_calcule_par_le_serveur`. |
| V2.3.1 | Verify that the application will only process business logic flows for the same user in the expected sequential step order and without skipping steps. | fait | J7 | Machine à états des commandes appliquée par l'API (reçue → acceptée → en préparation → prête → remise ; refus depuis « reçue », annulation en cours, gérante ou admin) ; transition absente du tableau = 409, commande verrouillée (SELECT … FOR UPDATE) ; remise d'une livraison impossible avant l'appel au client ; encaissement unique. Preuve : `apps/api/src/snacki_api/caisse.py, apps/api/tests/test_caisse.py::test_transitions_interdites`. |

## V3 · Web Frontend Security

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V3.2.1 | Verify that security controls are in place to prevent browsers from rendering content or functionality in HTTP responses in an incorrect context (e.g., when … | fait | J5 | En-têtes nosniff, Content-Type exact et CSP sur toutes les réponses du web et de l'API ; vérifiés par les tests et par le contrôle de fumée de chaque déploiement. Preuve : `apps/api/tests/test_security.py, apps/web/tests/securite.test.ts, infra/gcp/deploy.sh`. |
| V3.2.2 | Verify that content intended to be displayed as text, rather than rendered as HTML, is handled using safe rendering functions (such as createTextNode or … | fait | J4 | Textes saisis (prénom, repère, remarque) affichés comme texte par React et ramenés sur une seule ligne dans le message WhatsApp (oneLine) ; aucune insertion HTML. Preuve : `apps/web/src/lib/validate.ts, apps/web/tests/commande.test.ts`. |
| V3.3.1 | Verify that cookies have the 'Secure' attribute set, and if the '\__Host-' prefix is not used for the cookie name, the '__Secure-' prefix must be used for the … | fait | J6 | Cookie de session __Host-snacki_session : Secure, HttpOnly, SameSite=Lax, Path=/, 8 h ; cookie de parcours OAuth de 10 min sur le même modèle. Preuve : `apps/web/src/lib/staff.ts, apps/web/tests/staff.test.ts`. |
| V3.4.1 | Verify that a Strict-Transport-Security header field is included on all responses to enforce an HTTP Strict Transport Security (HSTS) policy. A maximum age of … | fait | J5 | Strict-Transport-Security: max-age=31536000; includeSubDomains sur le web et l'API ; présence vérifiée à chaque déploiement. Preuve : `apps/web/next.config.ts, apps/api/src/snacki_api/main.py, infra/gcp/deploy.sh`. |
| V3.4.2 | Verify that the Cross-Origin Resource Sharing (CORS) Access-Control-Allow-Origin header field is a fixed value by the application, or if the Origin HTTP … | fait | J5 | API privée (IAM Cloud Run, 403 sans jeton), appelée seulement par le serveur web : aucun en-tête CORS servi. Preuve : `infra/gcp/setup-deploy.sh, infra/gcp/deploy.sh, docs/adr/0007-deploiement-cloud-run.md`. |
| V3.5.1 | Verify that, if the application does not rely on the CORS preflight mechanism to prevent disallowed cross-origin requests to use sensitive functionality, … | fait | J6 | Protection CSRF : SameSite=Lax + vérification de l'en-tête Origin (adresse publique configurée, jamais Host) sur chaque requête du staff qui modifie ; state OAuth contre le CSRF de connexion. Preuve : `apps/web/src/lib/staff.ts, apps/web/src/app/api/staff, apps/api/tests/test_staff.py`. |
| V3.5.2 | Verify that, if the application relies on the CORS preflight mechanism to prevent disallowed cross-origin use of sensitive functionality, it is not possible … | N/A |  | Snacki ne s'appuie pas sur le preflight CORS pour se protéger (voir V3.5.1). |
| V3.5.3 | Verify that HTTP requests to sensitive functionality use appropriate HTTP methods such as POST, PUT, PATCH, or DELETE, and not methods defined by the HTTP … | fait | J3 | Création en POST uniquement ; le suivi en GET est sans effet de bord, vérifié par test. Preuve : `apps/api/tests/test_orders.py : test_suivi_sans_effet_de_bord`. |

## V4 · API and Web Service

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V4.1.1 | Verify that every HTTP response with a message body contains a Content-Type header field that matches the actual content of the response, including the … | fait | J7 | Toutes les réponses de l'API sont du JSON avec charset fixé (Utf8JSONResponse) ; pas de flux SSE (suivi par interrogation périodique, ADR 0009). Preuve : `apps/api/tests/test_security.py::test_en_tetes_de_securite, apps/api/tests/test_caisse.py`. |
| V4.4.1 | Verify that WebSocket over TLS (WSS) is used for all WebSocket connections. | N/A |  | Pas de WebSocket : le temps réel utilise Server-Sent Events en HTTPS. |

## V5 · File Handling

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V5.2.1 | Verify that the application will only accept files of a size which it can process without causing a loss of performance or a denial of service attack. | N/A |  | Aucun téléversement de fichier dans l'application (l'import Excel est un script d'administration hors ligne). |
| V5.2.2 | Verify that when the application accepts a file, either on its own or within an archive such as a zip file, it checks if the file extension matches an … | N/A |  | Aucun téléversement de fichier dans l'application. |
| V5.3.1 | Verify that files uploaded or generated by untrusted input and stored in a public folder, are not executed as server-side program code when accessed directly … | N/A |  | Aucun fichier fourni par un utilisateur n'est stocké. |
| V5.3.2 | Verify that when the application creates file paths for file operations, instead of user-submitted filenames, it uses internally generated or trusted data, or … | N/A |  | Aucun chemin de fichier construit à partir d'une saisie. |

## V6 · Authentication

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V6.1.1 | Verify that application documentation defines how controls such as rate limiting, anti-automation, and adaptive response, are used to defend against attacks … | fait | J1 | Limites de débit et anti-automatisation documentées (section 6 du modèle de menaces). Preuve : `docs/security/threat-model.md#6`. |
| V6.2.1 | Verify that user set passwords are at least 8 characters in length although a minimum of 15 characters is strongly recommended. | N/A |  | Aucun mot de passe : le staff se connecte uniquement par Google OAuth, les clients n'ont pas de compte. |
| V6.2.2 | Verify that users can change their password. | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.2.3 | Verify that password change functionality requires the user's current and new password. | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.2.4 | Verify that passwords submitted during account registration or password change are checked against an available set of, at least, the top 3000 passwords which … | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.2.5 | Verify that passwords of any composition can be used, without rules limiting the type of characters permitted. There must be no requirement for a minimum … | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.2.6 | Verify that password input fields use type=password to mask the entry. Applications may allow the user to temporarily view the entire masked password, or the … | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.2.7 | Verify that "paste" functionality, browser password helpers, and external password managers are permitted. | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.2.8 | Verify that the application verifies the user's password exactly as received from the user, without any modifications such as truncation or case transformation. | N/A |  | Aucun mot de passe géré par Snacki. |
| V6.3.1 | Verify that controls to prevent attacks such as credential stuffing and password brute force are implemented according to the application's security … | fait | J6 | Mots de passe gérés par Google ; limite de débit sur /v1/auth/* (10/min, 30/h) ; seules les adresses de la table staff_user sont acceptées. Preuve : `apps/api/src/snacki_api/ratelimit.py, apps/api/tests/test_staff.py`. |
| V6.3.2 | Verify that default user accounts (e.g., "root", "admin", or "sa") are not present in the application or are disabled. | fait | J6 | Aucun compte par défaut : la table du staff part vide ; le premier admin est créé par le job de migration à partir de SNACKI_BOOTSTRAP_ADMIN_EMAIL, une seule fois. Preuve : `apps/api/src/snacki_api/manage.py, apps/api/src/snacki_api/staff.py`. |
| V6.4.1 | Verify that system generated initial passwords or activation codes are securely randomly generated, follow the existing password policy, and expire after a … | N/A |  | Aucun mot de passe initial ni code d'activation générés. |
| V6.4.2 | Verify that password hints or knowledge-based authentication (so-called "secret questions") are not present. | N/A |  | Aucune question secrète ni indice de mot de passe. |

## V7 · Session Management

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V7.2.1 | Verify that the application performs all session token verification using a trusted, backend service. | fait | J6 | La session est vérifiée uniquement par l'API (signature, audience, expiration, version), jamais par le web. Preuve : `apps/api/src/snacki_api/main.py (require_role)`. |
| V7.2.2 | Verify that the application uses either self-contained or reference tokens that are dynamically generated for session management, i.e. not using static API … | fait | J6 | Jeton de session signé par l'API à chaque connexion, clé de 48 octets aléatoires dans Secret Manager ; aucune clé d'API statique pour le staff. Preuve : `apps/api/src/snacki_api/auth.py, infra/gcp/setup-auth.sh`. |
| V7.2.3 | Verify that if reference tokens are used to represent user sessions, they are unique and generated using a cryptographically secure pseudo-random number … | fait | J6 | Jeton de suivi : secrets.token_urlsafe (128 bits) ; state, nonce et vérificateur PKCE : secrets (192 à 256 bits). Preuve : `apps/api/src/snacki_api/orders.py, apps/api/src/snacki_api/auth.py`. |
| V7.2.4 | Verify that the application generates a new session token on user authentication, including re-authentication, and terminates the current session token. | fait | J6 | Nouveau jeton de session à chaque connexion ; la déconnexion, un changement de rôle ou une désactivation révoquent toutes les sessions du compte (version de session). Preuve : `apps/api/src/snacki_api/staff.py, apps/api/tests/test_staff.py`. |
| V7.4.1 | Verify that when session termination is triggered (such as logout or expiration), the application disallows any further use of the session. For reference … | fait | J6 | Déconnexion : la version de session du compte augmente, l'API refuse aussitôt les anciens jetons ; durée de vie maximale 8 h. Preuve : `apps/api/tests/test_staff.py (test_deconnexion_invalide_la_session)`. |
| V7.4.2 | Verify that the application terminates all active sessions when a user account is disabled or deleted (such as an employee leaving the company). | fait | J6 | Le compte et son rôle sont relus en base à chaque requête : désactivation ou changement de rôle effectifs immédiatement. Preuve : `apps/api/tests/test_staff.py (test_desactivation_immediate)`. |

## V8 · Authorization

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V8.1.1 | Verify that authorization documentation defines rules for restricting function-level and data-specific access based on consumer permissions and resource … | fait | J1 | Matrice des droits par rôle et règles d'accès aux données documentées (section 5 du modèle de menaces). Preuve : `docs/security/threat-model.md#5`. |
| V8.2.1 | Verify that the application ensures that function-level access is restricted to consumers with explicit permissions. | fait | J6 | Dépendance require_role() sur chaque route du staff ; un test échoue si une route non publique n'en a pas. Preuve : `apps/api/tests/test_staff.py (test_chaque_route_non_publique_exige_un_role)`. |
| V8.2.2 | Verify that the application ensures that data-specific access is restricted to consumers with explicit permissions to specific data items to mitigate insecure … | fait | J3 | Commande lisible seulement avec son jeton de suivi (128 bits, stocké haché, 24 h) ; même réponse 404 pour un jeton inconnu, expiré ou mal formé ; tests d'accès croisé. Preuve : `apps/api/tests/test_orders.py : test_un_jeton_n_ouvre_que_sa_commande, test_jeton_invalide_meme_reponse, test_jeton_expire`. |
| V8.3.1 | Verify that the application enforces authorization rules at a trusted service layer and doesn't rely on controls that an untrusted consumer could manipulate, … | fait | J6 | Tous les contrôles d'accès dans l'API ; le web ne fait que masquer des sections. Preuve : `apps/api/src/snacki_api/main.py, apps/web/src/lib/staff.ts (sectionsFor)`. |

## V9 · Self-contained Tokens

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V9.1.1 | Verify that self-contained tokens are validated using their digital signature or MAC to protect against tampering before accepting the token's contents. | fait | J6 | Jetons vérifiés par signature (PyJWT) avant toute lecture du contenu : sessions, parcours OAuth, jetons d'identité Google. Preuve : `apps/api/src/snacki_api/auth.py`. |
| V9.1.2 | Verify that only algorithms on an allowlist can be used to create and verify self-contained tokens, for a given context. The allowlist must include the … | fait | J6 | Algorithmes imposés : HS256 pour les jetons de l'API, RS256 pour Google ; « none » et la confusion HS256/RS256 refusés, testés. Preuve : `apps/api/tests/test_staff.py`. |
| V9.1.3 | Verify that key material that is used to validate self-contained tokens is from trusted pre-configured sources for the token issuer, preventing attackers from … | fait | J6 | Clé de session lue dans Secret Manager ; jetons d'identité Google vérifiés avec les clés publiées par Google (JWKS), audience et émetteur contrôlés. Preuve : `apps/api/src/snacki_api/auth.py`. |
| V9.2.1 | Verify that, if a validity time span is present in the token data, the token and its content are accepted only if the verification time is within this … | fait | J6 | exp vérifié (et iat exigé pour Google), tolérance d'horloge de 30 s sur les jetons Google ; sessions et parcours expirés refusés, testés. Preuve : `apps/api/tests/test_staff.py`. |

## V10 · OAuth and OIDC

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V10.4.1 | Verify that the authorization server validates redirect URIs based on a client-specific allowlist of pre-registered URIs using exact string comparison. | N/A |  | Snacki n'est pas serveur d'autorisation : Google l'est. URI de redirection enregistrées à l'identique dans la console Google (J6). |
| V10.4.2 | Verify that, if the authorization server returns the authorization code in the authorization response, it can be used only once for a token request. For the … | N/A |  | Serveur d'autorisation tiers (Google). |
| V10.4.3 | Verify that the authorization code is short-lived. The maximum lifetime can be up to 10 minutes for L1 and L2 applications and up to 1 minute for L3 … | N/A |  | Serveur d'autorisation tiers (Google). |
| V10.4.4 | Verify that for a given client, the authorization server only allows the usage of grants that this client needs to use. Note that the grants 'token' (Implicit … | N/A |  | Serveur d'autorisation tiers (Google). |
| V10.4.5 | Verify that the authorization server mitigates refresh token replay attacks for public clients, preferably using sender-constrained refresh tokens, i.e., … | N/A |  | Serveur d'autorisation tiers ; Snacki ne demande pas de jeton de rafraîchissement. |

## V11 · Cryptography

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V11.3.1 | Verify that insecure block modes (e.g., ECB) and weak padding schemes (e.g., PKCS#1 v1.5) are not used. | prévu | J12 | Aucun chiffrement maison : TLS et bibliothèques reconnues uniquement ; règle Semgrep sur les modes ECB. |
| V11.3.2 | Verify that only approved ciphers and modes such as AES with GCM are used. | prévu | J14 | Export de sauvegarde chiffré en AES-GCM (bibliothèque cryptography). |
| V11.4.1 | Verify that only approved hash functions are used for general cryptographic use cases, including digital signatures, HMAC, KDF, and random bit generation. … | fait | J6 | SHA-256 et HMAC-SHA-256 uniquement (jeton de suivi, PKCE S256, signatures HS256) ; Bandit (B303, B324) dans pre-commit et la CI. Preuve : `apps/api/src/snacki_api/auth.py, .pre-commit-config.yaml`. |

## V12 · Secure Communication

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V12.1.1 | Verify that only the latest recommended versions of the TLS protocol are enabled, such as TLS 1.2 and TLS 1.3. The latest version of the TLS protocol must be … | à vérifier | J14 | TLS géré par Google (Cloud Run) et Neon : versions mesurées avec testssl.sh et consignées dans le rapport de pentest. |
| V12.2.1 | Verify that TLS is used for all connectivity between a client and external facing, HTTP-based services, and does not fall back to insecure or unencrypted … | fait | J5 | HTTPS uniquement (Cloud Run), HSTS ; base Neon en sslmode=require, imposé par la configuration de l'API en staging et en production ; web → API en HTTPS. Preuve : `apps/api/src/snacki_api/config.py, infra/gcp/setup-deploy.sh`. |
| V12.2.2 | Verify that external facing services use publicly trusted TLS certificates. | fait | J5 | Certificats publics gérés par Google sur *.run.app. Preuve : `docs/adr/0007-deploiement-cloud-run.md`. |

## V13 · Configuration

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V13.4.1 | Verify that the application is deployed either without any source control metadata, including the .git or .svn folders, or in a way that these folders are … | fait | J5 | Images multi-étapes : .dockerignore en liste blanche côté API ; aucune copie de .git, des tests ni de .env, vérifié en CI à chaque PR ; npm et pip retirés des images finales. Preuve : `apps/api/Dockerfile, apps/web/Dockerfile, .github/workflows/ci.yml (job image)`. |

## V14 · Data Protection

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V14.2.1 | Verify that sensitive data is only sent to the server in the HTTP message body or header fields, and that the URL and query string do not contain sensitive … | fait | J4 | API : jeton reçu dans l'en-tête X-Tracking-Token, refusé dans l'URL. Front : lien /suivi#jeton, le fragment n'est jamais envoyé au serveur ; la page le lit et l'envoie en en-tête. Aucune donnée personnelle dans les URL. Preuve : `apps/api/tests/test_orders.py::test_jeton_refuse_dans_l_url, apps/web/src/lib/token.ts, apps/web/tests/securite.test.ts`. |
| V14.3.1 | Verify that authenticated data is cleared from client storage, such as the browser DOM, after the client or session is terminated. The 'Clear-Site-Data' HTTP … | fait | J6 | Déconnexion : cookie supprimé et en-tête Clear-Site-Data "cache", "storage". Preuve : `apps/web/src/app/auth/logout/route.ts`. |

## V15 · Secure Coding and Architecture

| ID | Exigence | Statut | Jour | Contrôle ou raison |
| --- | --- | --- | --- | --- |
| V15.1.1 | Verify that application documentation defines risk based remediation time frames for 3rd party component versions with vulnerabilities and for updating … | fait | J1 | Délais de correction documentés : critique 7 jours, haute 30 jours, moyenne 90 jours. Preuve : `SECURITY.md`. |
| V15.2.1 | Verify that the application only contains components which have not breached the documented update and remediation time frames. | fait | J5 | Porte 6 : pip-audit (strict) et npm audit (hautes et critiques) bloquants ; porte 7 : Trivy bloque toute faille haute ou critique corrigible dans les images ; Dependabot (pip, npm, docker, actions) chaque lundi. Preuve : `.github/workflows/ci.yml (jobs deps et image), .github/dependabot.yml`. |
| V15.3.1 | Verify that the application only returns the required subset of fields from a data object. For example, it should not return an entire data object, as some … | fait | J2 | Schémas de réponse Pydantic dédiés (response_model) : jamais d'objet de base de données renvoyé tel quel ; test qui fige la liste des champs publics. Preuve : `apps/api/src/snacki_api/schemas.py, apps/api/tests/test_menu.py::test_reponse_limitee_aux_champs_publics`. |
