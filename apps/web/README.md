# Front client Snacki (Next.js)

État : **J7** · menu FR/AR, panier, commande envoyée directement en caisse, suivi en direct, espace staff (`/staff`), caisse (`/caisse`).

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
- **Lien WhatsApp** : simple contact, message prérempli avec le seul numéro de commande (motif vérifié), jamais le jeton de suivi.
- **Caisse** : les boutons affichés dépendent du rôle et de l'état (`lib/caisse.ts`), mais l'API décide ; le relais `/api/caisse/orders/[id]/[action]` vérifie l'origine, l'identifiant et une liste blanche d'actions.
- **En-têtes** (`next.config.ts`) : `nosniff`, `DENY`, `no-referrer`, HSTS, `Permissions-Policy`.
