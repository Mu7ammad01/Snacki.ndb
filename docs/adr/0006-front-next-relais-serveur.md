# ADR 0006 · Front Next.js : design de l'étape 1 conservé, appels à l'API par le serveur web

Date : 1er octobre 2026 · Statut : accepté

## Contexte

L'app client de l'étape 1 (HTML, CSS et JavaScript sans framework) a un design validé par l'équipe. Le plan v3 prévoit Next.js et Tailwind, et une API Python que le navigateur n'appelle pas directement (ADR 0001).

## Décisions

1. **Next.js (App Router, TypeScript), sans Tailwind** : la feuille de style validée à l'étape 1 est reprise telle quelle ; la réécrire en classes Tailwind n'apporterait rien au client et ajouterait une dépendance.
2. **Le serveur web relaie** les appels (`/api/orders`, `/api/track`) : le navigateur ne connaît pas l'adresse de l'API, qui deviendra privée à J5 (IAM Cloud Run).
3. **Adresse du client transmise** dans `X-Forwarded-For` (dernier élément ajouté par le proxy le plus proche). L'API ne la croit que si `SNACKI_TRUST_FORWARDED_FOR=true`, à activer seulement quand elle n'est joignable que par le serveur web.
4. **CSP à nonce** posée par `src/proxy.ts` : toutes les pages sont rendues à la demande (pas de pages statiques), en échange d'une protection forte contre l'injection de script.

## Conséquences

- Le menu est toujours à jour (prix, disponibilités) ; une panne de l'API affiche un message et le numéro WhatsApp.
- À J5 : vérifier sur Cloud Run quel élément de `X-Forwarded-For` est fiable, puis activer `SNACKI_TRUST_FORWARDED_FOR` sur l'API.
