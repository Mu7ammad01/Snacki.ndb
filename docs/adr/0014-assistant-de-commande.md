# ADR 0014 · Assistant de commande (message WhatsApp → vente au comptoir)

- Statut : accepté (J9, 6 octobre 2026). Complète l'ADR 0004 (données envoyées à l'IA).
- Contexte : beaucoup de commandes arrivent par WhatsApp, en français, en arabe, en hassaniya, avec des fautes. La caissière les recopie à la main.

## Décision

1. En caisse, « Message WhatsApp » : la caissière colle le message, `POST /v1/caisse/assistant` (staff seulement, 10 par minute et 100 par heure) renvoie une **proposition** ; « Remplir la vente au comptoir » pré-remplit le formulaire existant. **Rien n'est créé sans validation humaine.**
2. Deux moteurs :
   - **Gemini** si la clé existe (`SNACKI_GEMINI_API_KEY`, secret `snacki-gemini-key-<env>`, activé par la variable GitHub `GEMINI_ENABLED_<ENV>`) : sortie JSON imposée par un schéma, identifiants de produits en **liste fermée**, température 0 ;
   - **analyse locale** (mots-clés FR, AR, hassaniya, quantités en chiffres et en mots) : sans clé, ou si Gemini échoue ou dépasse 10 s.
3. **T13 · injection de prompt** : le message est une donnée encadrée, jamais une consigne ; le modèle ne renvoie que des identifiants et des quantités ; les prix viennent de la base ; quantités bornées (1 à 20, 9 lignes) ; la caissière valide.
4. **T14 · données personnelles** : téléphones et e-mails remplacés par `[TEL]` et `[EMAIL]` avant l'appel ; le message n'est jamais enregistré (le journal d'audit garde le moteur, le nombre de lignes et la longueur).
5. Jeu d'évaluation : `apps/api/tests/data/assistant_eval.json` (24 messages, dont 2 pièges), joué à chaque CI sur l'analyse locale ; les 60 messages réels anonymisés s'y ajouteront.

## Conséquences

- L'assistant marche dès aujourd'hui sans clé ; Gemini améliore les messages libres (fautes, tournures).
- Limite connue : un prénom écrit dans le message part vers Gemini (seuls numéros et e-mails sont masqués). Offre gratuite de Gemini : Google peut utiliser les données pour améliorer ses modèles ; d'où le masquage et l'absence de toute donnée de compte.
- Coût : offre gratuite de Gemini, protégée par la limite de débit (T15 traité en J10).
