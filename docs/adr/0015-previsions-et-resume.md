# ADR 0015 · Prévisions de ventes et résumé du jour

- Statut : accepté (J10, 6 octobre 2026). Complète l'ADR 0010 (pilotage) et l'ADR 0014 (IA).
- Contexte : la gérante veut savoir combien préparer (fruits, crêpes) et avoir un bilan du jour lisible en 10 secondes, sans tableur.

## Décision

1. **Prévisions** (`GET /v1/pilotage/previsions`, gérante et admin) : aujourd'hui et les 6 jours suivants, par produit. Modèle simple et explicable, en Python pur (pas de scikit-learn : une dépendance lourde de moins à surveiller) :
   - moyenne pondérée des mêmes jours de semaine des 4 dernières semaines ouvertes (poids 4, 3, 2, 1) ;
   - sinon, moyenne des 14 derniers jours ouverts ; un jour sans vente est un jour de fermeture ;
   - sources : ventes encaissées (app et comptoir) et historique Excel, 12 semaines au plus.
2. **Contrôle du modèle** : « backtest » sur les 4 dernières semaines contre la méthode naïve « comme le même jour la semaine dernière ». Fiabilité affichée : *bonne* (fait mieux, 8 jours comparés au moins), *indicative*, ou *insuffisante* (moins de 14 jours de ventes).
3. **Résumé du jour** (`GET /v1/pilotage/resume?day=…&ia=…`) : faits calculés par SQL, texte modèle déterministe par défaut. Bouton « Reformuler avec l'IA » : Gemini reçoit les seuls agrégats (aucun nom, téléphone, message).
4. **T16 · chiffre inventé** : chaque nombre du texte de l'IA doit figurer dans les faits (ou la date) ; décimaux et nombres en lettres refusés ; sinon le texte modèle est affiché avec un avertissement.
5. **T15 · quota** : plafond quotidien par usage, dans PostgreSQL (table `ai_usage`, migration 0009), commun à toutes les instances : 200 analyses de l'assistant (`SNACKI_AI_CAP_ASSISTANT`) et 20 résumés (`SNACKI_AI_CAP_RESUME`). Au-delà : analyse locale ou résumé modèle, avec un avertissement. Cache des résumés déjà vérifiés ; limite de débit `resume` (10 par minute, 60 par heure).

## Conséquences

- Les prévisions sont « insuffisantes » tant que l'app et l'historique couvrent moins de 14 jours de ventes ; elles s'améliorent seules.
- Les jours fériés et le ramadan ne sont pas modélisés : la gérante corrige à l'œil (limite affichée).
- La vérification des nombres peut écarter une bonne reformulation (par exemple « 4,2 milliers ») : on préfère un texte standard à un chiffre faux.
