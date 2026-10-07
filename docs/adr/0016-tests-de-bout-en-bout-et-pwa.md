# ADR 0016 · Tests de bout en bout et application installable

- Statut : accepté (J11, 7 octobre 2026). Complète l'ADR 0006 (front Next.js) et l'ADR 0007 (déploiement).
- Contexte : les tests unitaires vérifient chaque brique, pas l'enchaînement réel « le client commande, la caisse sert ». Et la caisse veut ouvrir l'app comme une application, sans page d'erreur du navigateur quand le réseau coupe.

## Décision

1. **Tests de bout en bout** (Playwright, `apps/web/e2e/`) : Chromium au format téléphone, sur l'app **construite en mode production**, l'API et un PostgreSQL jetables (job `e2e` de la CI ; sa réussite conditionne le déploiement). Quatre parcours :
   - client : menu, panier, commande à emporter, suivi, sans aucun blocage CSP ;
   - caisse : accepter, préparer, encaisser, remettre ; le client voit l'avancement ;
   - sécurité : pilotage réservé (redirection, refus au caissier), CSP à nonce, `X-Frame-Options` ;
   - PWA : manifestes, page hors connexion, contenu du cache.
2. **Pas de porte dérobée** : la connexion du staff est simulée par un vrai jeton de session signé avec la clé de la CI (`e2e/staff_session.py`, refusé hors environnement `test`). L'app ne contient aucun code propre aux tests. Le lien WhatsApp n'est jamais ouvert.
3. **Application installable** : manifeste client (`/`) et manifeste caisse (`/manifest-caisse.webmanifest`, s'ouvre sur `/caisse`). Service worker `/sw.js` (CSP : `worker-src 'self'`) :
   - ne met en cache **que** des fichiers publics (scripts et styles versionnés, images, icônes, polices) ;
   - **jamais** une page ni une réponse d'API : aucune commande, aucun numéro de client ni écran de caisse ne reste sur le téléphone ;
   - sans réseau, une navigation affiche `/offline.html` (FR et AR).

## Conséquences

- Une régression qui casse le parcours réel bloque la PR, même si chaque test unitaire passe.
- La caisse ne fonctionne pas hors connexion (choix assumé : une commande doit être enregistrée par l'API) ; l'écran le dit clairement.
- Mise à jour du service worker : changer `CACHE` dans `sw.js` vide l'ancien cache à l'activation.
