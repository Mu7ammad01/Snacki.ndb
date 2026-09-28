# ADR 0004 · Données envoyées à l'IA

- Statut : acceptée (J1, 27/09/2026), issue du modèle de menaces (T13, T14)

## Contexte

L'assistant de commande envoie le texte d'un message WhatsApp à l'API Gemini. Sur l'offre gratuite, Google indique que les contenus peuvent servir à améliorer ses produits ([tarifs Gemini](https://ai.google.dev/gemini-api/docs/pricing)). Un message contient souvent un prénom, un numéro et un repère de livraison.

## Décision

1. Avant l'appel, l'API remplace les numéros de téléphone par `[TEL]`, le prénom connu du client par `[CLIENT]`, et supprime le repère de livraison.
2. Seule la version masquée est stockée (table `ai_suggestion`), 30 jours.
3. Le LLM reçoit la liste des produits (identifiants et noms), jamais les prix ; il renvoie un JSON validé par Pydantic ; un humain confirme.
4. Un test (porte 8, J9) échoue si un numéro mauritanien à 8 chiffres atteint la requête envoyée à Gemini.
5. Si Snacki passe un jour à l'offre payante (contenus non utilisés par Google), le masquage reste : il ne coûte rien et limite l'exposition.

## Conséquences

- Positif : aucune donnée personnelle ne sort vers un tiers ; l'injection de prompt ne peut pas changer un prix.
- Négatif : le masquage peut retirer un mot utile (un prénom qui est aussi un nom de produit) ; mesuré par le jeu d'évaluation de 60 messages.
