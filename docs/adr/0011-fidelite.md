# ADR 0011 · Fidélité : carte à numéro unique, tampons enregistrés dans l'app

Date : 5 octobre 2026 · Statut : accepté

## Contexte

La gérante veut récompenser les clients réguliers : tous les 5 achats, une commande offerte jusqu'à 100 MRU. Une carte papier tamponnée se fraude facilement (tampon imité, cases cochées au stylo, carte photocopiée). Décisions de Mike (5 octobre 2026) : achats comptés **dans l'app seulement**, téléphone **facultatif**, chantier fait **avant J9**. Menace visée : T28.

## Décisions

1. **Numéro unique** imprimé en clair et dans un QR sur une étiquette collée au verso du menu : `FID-7KQ2-M9XA`. 7 caractères aléatoires (base 32 de Crockford, sans I, L, O, U ; `secrets`) + 1 caractère de contrôle Luhn mod 32. Une faute de frappe est refusée tout de suite ; un numéro inventé n'est presque jamais valide, et **seules les cartes émises par Snacki existent en base**.
2. **Le QR ouvre `/carte#FID-…`** : le client suit ses achats ; le numéro reste dans le fragment (jamais dans l'URL envoyée au serveur), part dans le corps d'une requête POST ; la réponse ne contient aucune donnée personnelle ; limite de débit (20 par minute, 200 par heure).
3. **Tampons dans la base seulement**, donnés par le staff après l'encaissement : une commande = un tampon (contrainte d'unicité), 3 tampons au plus par carte et par jour, 10 minutes au moins entre deux. La commande offerte ne donne pas de tampon.
4. **Cadeau** appliqué avant l'encaissement : 100 MRU au plus retirés de la commande (`discount_mru`, contrôlé aussi par la base) ; la carte est verrouillée pendant l'action (deux caisses, un seul cadeau).
5. **Annulation** d'une commande (gérante) : son tampon est retiré, ou les 5 tampons de son cadeau sont rendus.
6. **Gérante et admin** : bloquer une carte, reporter les tampons d'une carte perdue sur une carte neuve, retrouver une carte par le téléphone du client.
7. **Grand livre** (`loyalty_event`) de chaque mouvement, avec auteur et commande, plus le journal d'audit ; le pilotage affiche tampons, cadeaux et montant offert.
8. **Lecture du QR à la caisse** avec la caméra du téléphone (BarcodeDetector), sans bibliothèque ni envoi d'image ; la caméra n'est autorisée que sur `/caisse` (Permissions-Policy). Sans caméra : saisie du numéro.
9. **Impression** par script (`manage loyalty-cards`) : par défaut, cartes complètes (verso du menu) avec QR et numéro uniques déjà imprimés, 2 par page A4, traits de coupe ; ou planches de 44 étiquettes 48,5 × 25,4 mm à coller sur des menus déjà imprimés. Le fond (`apps/api/print/carte-verso.jpg`) est le rendu de la maquette ; le PDF contient des numéros valides, il reste hors du dépôt et se supprime après impression.
10. **Téléphone** facultatif, effacé après 1 an sans achat (conservation, J8).

## Conséquences

- Le numéro est stocké en clair : il ne donne aucun droit sans le staff (tampon, cadeau) et ne révèle que la progression. Un hachage n'apporterait rien avec 35 bits d'aléa (cassable hors ligne) ; risque accepté, revu avec la sauvegarde chiffrée (J14).
- Un caissier complice reste le risque principal : il est borné par les limites par jour et l'unicité par commande, et visible dans le grand livre et le pilotage.
- Une carte copiée (photo du QR) peut être utilisée par un tiers : la limite par jour borne l'abus ; la carte se bloque et se remplace.
