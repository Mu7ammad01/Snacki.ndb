# ADR 0009 · Caisse : commande uniquement dans l'app, cycle de vie appliqué par l'API, suivi par interrogation

Date : 6 octobre 2026 · Statut : accepté · Remplace le point « suivi en flux SSE » de l'ADR 0003

## Contexte

Jusqu'à J6, le client terminait sa commande en l'envoyant au snack par WhatsApp, et le staff la confirmait dans la conversation. À J7, la caisse arrive. La gérante a tranché le 3 octobre 2026 :

1. refuser ou annuler une commande : gérante ou admin, jamais le caissier ;
2. la gérante est aussi admin ;
3. les frais de livraison sont fixés à chaque commande ;
4. avant de livrer, on appelle le client ;
5. la commande passe uniquement par l'app ; WhatsApp devient un lien de contact pour rebondir en cas de besoin.

Menaces visées : T04, T11, T25 (nouvelle), ASVS V2.3.1.

## Décisions

1. **Machine à états dans l'API** (`caisse.py`) :

   ```
   reçue ──accepter──▶ acceptée ──▶ en préparation ──▶ prête ──▶ remise
     │                    │               │              │
     └─refuser            └───────────── annuler ────────┘   (gérante ou admin)
   ```

   Toute transition absente du tableau est refusée (409), quel que soit l'écran qui la demande. La commande est verrouillée (`SELECT … FOR UPDATE`) pendant l'action : deux caissiers ne la modifient pas en même temps.
2. **Accepter = s'engager** : délai de préparation (5 à 120 min) et, pour une livraison, frais obligatoires (0 à 2000 MRU) ; jamais de frais à emporter. Le client voit l'heure prévue et le total à payer (`grand_total_mru`).
3. **Appel avant livraison** : une livraison ne peut pas passer à « remise » tant que « client appelé » n'a pas été marqué (409). Le numéro est cliquable (`tel:`) dans la caisse.
4. **Refus et annulation** : routes protégées par `require_role(gérante, admin)` ; motif obligatoire (3 à 160 caractères), montré au client. Refus seulement depuis « reçue », annulation seulement d'une commande en cours.
5. **Encaissement unique** : un moyen parmi espèces, Bankily, Sedad, Bimbank, Bamis ; impossible sur une commande reçue, refusée ou annulée. Pas de remboursement dans l'app (risque accepté, voir le modèle de menaces).
6. **Vente au comptoir** : même numérotation que l'app, créée directement « en préparation », sans téléphone ; seuls produits et quantités sont envoyés, l'API fixe les prix (T01).
7. **Journal d'audit** de chaque action (auteur, commande, détail : délai, frais, avant/après, moyen, montant, motif, déjà payée) : T11 traitée.
8. **Interrogation périodique au lieu de SSE** : la caisse relit les commandes du jour toutes les 5 s, le suivi client toutes les 10 s. Raisons : Cloud Run coupe les requêtes longues et peut lancer 2 instances sans bus d'événements commun ; l'API est privée derrière le web (un flux devrait traverser deux services) ; le trafic d'un snack est faible. Le jeton de suivi reste en en-tête (T03 inchangée).
9. **WhatsApp n'est plus qu'un lien de contact** : message prérempli avec le seul numéro de commande (motif `SNK-AAAA-NNN` vérifié), jamais le jeton de suivi ni le panier. Le bouton « Confirmer sur WhatsApp » disparaît.
10. **Alertes de la caisse** : bip généré par le navigateur et notification système, activés par un geste du staff (exigence des navigateurs) ; rien n'est stocké dans le navigateur.

## Conséquences

- Sans la confirmation WhatsApp, l'identité du client n'est plus vérifiée à la commande : c'est l'acceptation par le staff et l'appel avant livraison qui jouent ce rôle (T25).
- La caisse doit rester ouverte sur un appareil pendant le service pour entendre les nouvelles commandes.
- La migration 0005 ajoute deux valeurs au type `order_status` ; son retour arrière recrée le type et supprime les ventes au comptoir.
- Plus tard : le pilotage (J8) s'appuie sur `paid_at`, `paid_method` et `grand_total_mru`.
