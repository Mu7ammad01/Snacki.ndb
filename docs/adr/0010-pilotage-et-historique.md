# ADR 0010 · Pilotage : historique Excel importé par script, chiffres calculés par l'API

Date : 7 octobre 2026 · Statut : accepté

## Contexte

Avant l'app, les ventes du snack étaient notées à la main dans un classeur Excel (« Suivi Dashboard », feuille « Ventes » : un bloc de colonnes par jour, une ligne par commande, texte libre comme « 2 crepes + 2 jus fraises », montant en ancienne ouguiya). La gérante veut voir dans un même écran le chiffre d'affaires, les produits les plus vendus et les moyens de paiement, historique compris. Le classeur contient aussi des feuilles d'associés (capital, parts) qui n'ont rien à faire dans l'app. Menaces visées : T26 (lecture des chiffres par un non-autorisé), T27 (fichier piégé), ASVS V1.5.1.

## Décisions

1. **Import par script d'administration**, jamais par téléversement web : `python -m snacki_api.manage import-history FICHIER.xlsx [--dry-run]`, lancé depuis le Codespace. La chaîne de connexion de la base est lue dans Secret Manager par `gcloud` au moment de la commande, sans jamais être affichée ni tapée.
2. **Feuille « Ventes » seule** : les autres feuilles ne sont jamais lues (minimisation).
3. **Montants divisés par 10** : le classeur compte en ancienne ouguiya (1 000 MRO = 100 MRU, prix d'une salade). L'option `--divisor 1` existe pour un futur classeur en MRU.
4. **Tables séparées** (`history_sale`, `history_item`), distinctes de `orders` : pas de faux numéros SNK, pas de jeton, pas de coordonnées, aucune interaction avec la caisse ou le suivi.
5. **Reconnaissance par mots-clés** du texte libre (salade, crêpe, avocat, mangue ou « mango », fraise, cocktail, orange…), quantité en tête de chaque morceau séparé par « + ». Ce qui n'est pas reconnu (desserts, « jus » sans précision, illisible) devient « hors menu » : le montant est compté dans le chiffre d'affaires, la quantité dans « Hors menu ». J9 pourra affiner ces cas avec l'IA.
6. **Import idempotent** : il remplace les jours présents dans le fichier, en une transaction. Relancer le même fichier ne double rien ; un fichier corrigé remplace les jours qu'il contient.
7. **Chiffres calculés par PostgreSQL** (`pilotage.py`, requêtes SQLAlchemy paramétrées) : commandes encaissées, ni refusées ni annulées, plus l'historique. Période validée (dates réelles, 366 jours au plus).
8. **Accès** : `GET /v1/pilotage` réservé à la gérante et à l'admin ; page `/pilotage` rendue par le serveur web, sans JavaScript, barres en SVG (la CSP interdit les styles en ligne).
9. **Conservation** (inventaire des données) : à chaque déploiement, le job de migration anonymise les commandes closes de plus de 90 jours (prénom, téléphone, repère, remarque) et supprime le journal d'audit de plus d'un an. Les montants et produits restent pour le pilotage.

## Conséquences

- Le classeur ne va jamais dans le dépôt public (`*.xlsx` dans `.gitignore`) : ce sont les chiffres du snack.
- L'historique n'a pas de prix par article ni de moyen de paiement : le top produits l'additionne en quantités seulement, les paiements ne concernent que l'app.
- Une commande anonymisée n'a plus de téléphone : la contrainte `phone_if_app` l'autorise désormais (`anonymized_at`).
- pandas, openpyxl et defusedxml ne servent qu'au script : ils restent hors de l'image de l'API (`requirements-dev.txt`).
