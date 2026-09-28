# ADR 0003 · Jeton de suivi dans le fragment de l'URL

- Statut : acceptée (J1, 27/09/2026), issue du modèle de menaces (T02, T03)

## Contexte

Le client suit sa commande sans compte, grâce à un lien. Le plan prévoyait `GET /orders/{jeton}/events`. Or un jeton placé dans le chemin de l'URL se retrouve dans l'historique du navigateur, les journaux des serveurs et l'en-tête `Referer` : l'ASVS l'interdit pour une donnée qui donne un accès (V14.2.1).

## Décision

1. Le lien envoyé au client est `https://…/suivi#t=<jeton>`. Le fragment (après `#`) n'est jamais envoyé au serveur ni journalisé.
2. La page lit le jeton dans le fragment, puis appelle l'API avec l'en-tête `X-Tracking-Token`.
3. Le suivi en direct utilise `fetch()` avec un flux (Server-Sent Events lus à la main), car `EventSource` ne permet pas d'envoyer un en-tête.
4. Le jeton fait 128 bits (`secrets.token_urlsafe(16)`), n'est stocké qu'haché (SHA-256), expire après 24 h et ne montre que le statut et les produits : jamais le téléphone ni le repère.
5. La page de suivi envoie `Referrer-Policy: no-referrer`.

## Conséquences

- Positif : un jeton qui fuit par une capture d'écran de l'URL reste le seul risque, et il ne révèle aucune donnée personnelle.
- Négatif : un peu plus de code côté front (lecture du flux SSE avec `fetch`).
