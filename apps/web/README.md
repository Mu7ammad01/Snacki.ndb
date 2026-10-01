# Front client Snacki (Next.js)

État : **J4** · menu FR/AR, panier, commande, confirmation WhatsApp, suivi de commande.

Le navigateur ne parle qu'au serveur web ; le serveur web appelle l'API Python (ADR 0001, ADR 0006).

| Route | Rôle |
| --- | --- |
| `/` | Menu lu dans l'API à chaque visite, panier, formulaire, confirmation |
| `/suivi#jeton` | Suivi d'une commande ; le jeton reste dans le fragment `#`, jamais envoyé au serveur |
| `POST /api/orders` | Relais vers `POST /v1/orders` (corps limité à 4 Ko, adresse du client transmise) |
| `GET /api/track` | Relais vers `GET /v1/orders/track`, jeton en en-tête `X-Tracking-Token` |

## Démarrer en local

L'API doit tourner sur le port 8000 (voir `apps/api/README.md`).

```bash
cd apps/web
npm ci
SNACKI_API_URL=http://localhost:8000 npm run dev    # http://localhost:3000
npm test                                            # Vitest
npx tsc --noEmit && npm run build                   # comme la CI
```

## Sécurité

- **CSP à nonce** (`src/proxy.ts`) : seuls les scripts portant le nonce de la requête s'exécutent (T06).
- **Aucun HTML brut** : un test parcourt les sources et refuse `dangerouslySetInnerHTML`, `innerHTML`, `eval`…
- **Total** : le navigateur affiche une estimation ; le total qui fait foi vient de l'API (T01).
- **Message WhatsApp** : construit avec le numéro et le total de l'API ; chaque saisie libre est ramenée sur une ligne.
- **En-têtes** (`next.config.ts`) : `nosniff`, `DENY`, `no-referrer`, HSTS, `Permissions-Policy`.
