# ADR 0018 · Achats, fournisseurs et stock des ingrédients

- Statut : accepté (J16, 25 octobre 2026). Demande du 25/10/2026 : gestion des achats par la gérante et les admins.
- Contexte : les dépenses du snack (fruits, gaz, gobelets…) ne sont suivies nulle part. Sans elles, le pilotage ne montre que les ventes, pas la marge. La v1.2 prévoit le stock par ingrédient : il faut d'abord savoir ce qui entre.

## Décision

1. **Quatre tables** (migration 0010) : `supplier`, `ingredient` (unité kg, litres ou pièces, stock, seuil d'alerte), `purchase` et `purchase_line`, plus `stock_move`, le grand livre du stock.
2. **Droits** : gérante et admin, mêmes droits (routes `/v1/achats…`, rôle relu à chaque requête, contrôle répété dans `achats.py`). Le caissier n'y a pas accès (T26).
3. **Total calculé par l'API** : la gérante saisit les lignes du ticket (quantité, montant) ; un champ « total » envoyé est refusé (`extra="forbid"`, comme T01).
4. **Rien n'est modifié ni effacé** : une erreur se corrige en annulant l'achat (motif obligatoire), puis en le saisissant à nouveau. L'achat annulé reste visible, barré, hors des totaux (T11).
5. **Stock** : une ligne liée à un ingrédient ajoute sa quantité au stock ; l'annulation la retire. L'inventaire remplace le stock par la quantité comptée, avec un motif. Chaque variation est écrite dans `stock_move` (avant, après, auteur, cause). Le stock ne peut jamais devenir négatif (contrainte en base et refus lisible). Les ingrédients sont verrouillés (`FOR UPDATE`) pendant la mise à jour : deux saisies simultanées ne perdent rien.
6. **Pilotage** : dépenses de la période par catégorie, fournisseur et jour ; **marge brute = chiffre d'affaires − achats** de la même période ; alertes de stock bas. Le rapport Excel gagne un onglet « Achats » (noms de fournisseurs écrits comme du texte, jamais comme des formules).
7. **Journal** : 7 nouvelles actions (achat enregistré ou annulé, fournisseur et ingrédient ajoutés ou modifiés, inventaire), dans la famille « Achats et stock » de l'historique.

## Conséquences

- La marge n'est juste qu'à partir du premier achat saisi : l'écran l'indique. L'historique Excel d'avant l'app n'a pas d'achats.
- La consommation des ingrédients par les ventes (recettes) n'est pas encore déduite : ce sera la v1.2. En attendant, l'inventaire régulier recale le stock.
- Photo du ticket : non incluse. Un envoi de fichier (taille, type, stockage, analyse) fera l'objet d'une étape dédiée.
