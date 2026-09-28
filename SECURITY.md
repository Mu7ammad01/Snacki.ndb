# Politique de sécurité

## Signaler une faille

Ne publiez jamais une faille dans une issue publique. Utilisez le formulaire privé de GitHub : onglet **Security** → **Report a vulnerability**.

Indiquez la page ou la route concernée, les étapes pour reproduire et l'impact que vous voyez. Merci de ne pas accéder aux données d'autres personnes au-delà de ce qui prouve la faille, et de ne pas lancer de test qui ralentit le service du snack.

## Délais de réponse

| Étape | Délai |
| --- | --- |
| Accusé de réception | 3 jours |
| Première évaluation (gravité, périmètre) | 7 jours |

## Délais de correction (ASVS V15.1.1)

Ces délais s'appliquent aux failles signalées, à celles trouvées par les portes de la CI et aux dépendances vulnérables. La gravité suit le score CVSS de l'alerte, ajusté au contexte de Snacki.

| Gravité | Délai maximal de correction en production |
| --- | --- |
| Critique | 7 jours |
| Haute | 30 jours |
| Moyenne | 90 jours |
| Faible | à la revue suivante du modèle de menaces |

Une dépendance hors délai bloque la CI (portes 6 et 7, à partir de J5). Une exception se documente dans le dépôt avec sa raison et une date d'expiration.

## Versions suivies

Seule la dernière version déployée en production reçoit des correctifs.

## Documentation de sécurité

- [Modèle de menaces](docs/security/threat-model.md)
- [Suivi OWASP ASVS 5.0 niveau 1](docs/security/asvs-l1.md)
- [Décisions d'architecture](docs/adr/)
