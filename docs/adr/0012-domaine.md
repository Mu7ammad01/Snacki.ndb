# ADR 0012 · Domaine public snackindb.com

- Statut : accepté (J8 ter, 5 octobre 2026)
- Contexte : l'adresse Cloud Run (`snacki-web-prod-…-uc.a.run.app`) est longue, impossible à dicter et peu rassurante pour un client. Elle est pourtant imprimée dans les QR des 152 premières cartes de fidélité.

## Décision

1. Domaine `snackindb.com`, acheté chez Cloudflare Registrar (prix coûtant, renouvellement au même prix), compte protégé par la validation en 2 étapes, verrou de transfert actif.
2. Liaison directe Cloud Run (`gcloud beta run domain-mappings`) pour `snackindb.com` et `www.snackindb.com`, certificat géré par Google. Enregistrements DNS en « DNS only » chez Cloudflare. Script : `infra/gcp/setup-domain.sh`.
3. **Une seule origine publique** : `SNACKI_PUBLIC_URL=https://snackindb.com` (variable GitHub `PUBLIC_URL_PROD`). Elle fixe l'adresse de retour OAuth et l'origine acceptée par la protection CSRF (T08).
4. L'ancienne adresse run.app et `www` restent actives et répondent **308** vers `https://snackindb.com` + chemin (`lib/canonical.ts`, appelé par `proxy.ts`). Le navigateur conserve le fragment : les QR imprimés (`…run.app/carte#FID-…`) continuent de fonctionner.
5. Staging garde son adresse run.app (pas de `PUBLIC_URL`).

## Options écartées

- Firebase Hosting (`snacki-ndb.web.app`, gratuit) : ne transmet qu'un cookie nommé `__session` ; casserait les cookies `__Host-` du staff.
- Équilibreur de charge global : stable et complet, mais environ 18 $ par mois, disproportionné pour un snack.
- Domaine `.mr` : démarches plus lentes ; à reconsidérer plus tard.

## Conséquences

- La liaison Cloud Run directe est en préversion chez Google : en cas de retrait, passer à l'équilibreur de charge sans changer le code (seul le DNS change).
- Le staff se reconnecte une fois (les cookies sont propres à chaque domaine).
- Nouvelle menace prise en compte : détournement du domaine (compte registrar, DNS). Parades : validation en 2 étapes, verrou de transfert, renouvellement automatique, DNS modifiable par Mike seul.
- La redirection ne lit jamais l'hôte pour construire sa destination : pas de redirection ouverte (tests `canonical.test.ts`).
