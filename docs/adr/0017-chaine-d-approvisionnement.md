# ADR 0017 · Chaîne d'approvisionnement : SBOM, images signées, scan ZAP

- Statut : accepté (J12, 7 octobre 2026). Complète l'ADR 0007 (déploiement) et la menace T20.
- Contexte : Trivy vérifie qu'une image n'a pas de faille connue, mais rien ne prouvait encore que l'image déployée est bien celle construite par la CI, ni ce qu'elle contient. Et l'application en ligne n'était jamais analysée de l'extérieur.

## Décision

1. **SBOM** (liste des composants) de chaque image au format CycloneDX, produit par Trivy (action déjà épinglée) dans le job `build`.
2. **Signature sans clé** (Sigstore cosign) : le job `build` signe chaque image par son empreinte et lui attache son SBOM comme attestation signée. L'identité est le jeton OIDC du job : pas de clé à garder ni à voler. Le certificat et la signature sont inscrits au journal public Rekor.
3. **Vérification avant chaque déploiement** (staging et production) : `cosign verify` et `cosign verify-attestation` exigent que le signataire soit exactement `deploy.yml` sur `main` de ce dépôt (émetteur GitHub Actions). Sinon, le job s'arrête avant de toucher Cloud Run.
4. **cosign** est installé par `go install …@v2.4.1` : le module est vérifié par la base publique de sommes de contrôle de Go, sans nouvelle action tierce. La version se met à jour à la main (variable `COSIGN_VERSION`).
5. **Porte 9 · OWASP ZAP baseline** sur staging (job `zap`), entre staging et la production : analyse passive de ce que voit un visiteur. Règles bloquantes dans `.zap/rules.tsv` (en-têtes CSP, HSTS, anti-cadre, type MIME, cookies HttpOnly, Secure, SameSite, X-Powered-By) ; les autres alertes s'affichent sans bloquer. Le job n'a ni jeton Google ni secret.
6. **Registre** : chaque version produit désormais 3 objets par image (image, signature, attestation). La règle de nettoyage garde les 9 derniers au lieu de 3, pour ne jamais effacer la signature d'une image encore en service.

## Conséquences

- Une image poussée à la main dans le registre, même par un compte Google valide, ne passe plus la vérification.
- Le déploiement prend 2 à 4 minutes de plus (installation de cosign, signature, scan ZAP).
- Limites : l'image ZAP suit l'étiquette `stable` (outil de test, sans secret, isolé) ; la vérification se fait dans le pipeline, pas dans Cloud Run lui-même (Binary Authorization reste une option).
