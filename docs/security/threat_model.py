#!/usr/bin/env python3
"""Modèle de menaces de Snacki « as code » (OWASP pytm).

Le schéma de flux de données (DFD) est généré à partir de ce fichier, il ne se dessine pas
à la main : quand l'architecture change, on modifie ce modèle dans la même PR.

    python3 docs/security/threat_model.py --dfd | dot -Tpng -o docs/security/dfd.png
    python3 docs/security/threat_model.py --seq     # diagramme de séquence (PlantUML)

La liste des menaces retenues, leurs risques et leurs parades est dans threat-model.md.
"""

from pytm import (
    TM,
    Actor,
    Boundary,
    Classification,
    Data,
    Dataflow,
    Datastore,
    ExternalEntity,
    Process,
    Server,
    TLSVersion,
)

tm = TM("Snacki PWA v3")
tm.description = (
    "PWA de commande et de gestion du snack Snacki (Nouadhibou). Clients sans compte, "
    "staff connecté par Google OAuth, API FastAPI, PostgreSQL Neon, IA Gemini."
)
tm.isOrdered = True
tm.mergeResponses = True
tm.assumptions = [
    "Google (Cloud Run, OAuth, Gemini) et Neon sont des fournisseurs de confiance.",
    "Le téléphone du staff est verrouillé par code et n'est pas partagé.",
    "Les paiements Bankily et espèces sont validés à la main : aucune donnée bancaire dans Snacki.",
]

# --- Frontières de confiance -------------------------------------------------
internet = Boundary("Internet (non fiable)")
gcp = Boundary("Google Cloud Run · projet Snacki")
third = Boundary("Services tiers")
supply = Boundary("Chaîne de build (GitHub)")

# --- Acteurs ------------------------------------------------------------------
client = Actor("Client (sans compte)")
client.inBoundary = internet

staff = Actor("Staff (caissier, gérante, admin)")
staff.inBoundary = internet

dev = Actor("Développeur")
dev.inBoundary = supply

# --- Processus et magasins ----------------------------------------------------
web = Server("web · Next.js (PWA)")
web.inBoundary = gcp
web.OS = "Linux (conteneur non-root)"
web.protocol = "HTTPS"

api = Process("api · FastAPI (Python)")
api.inBoundary = gcp
api.usesEnvironmentVariables = True
api.usesSessionTokens = True

secrets = Datastore("Secret Manager")
secrets.inBoundary = gcp
secrets.storesSensitiveData = True

db = Datastore("PostgreSQL (Neon)")
db.inBoundary = third
db.isSQL = True
db.storesPII = True
db.storesLogData = True
db.hasWriteAccess = True

oauth = ExternalEntity("Google OAuth 2.0")
oauth.inBoundary = third

gemini = ExternalEntity("API Gemini")
gemini.inBoundary = third

whatsapp = ExternalEntity("WhatsApp (wa.me)")
whatsapp.inBoundary = third

ci = Process("GitHub Actions")
ci.inBoundary = supply

# --- Données ------------------------------------------------------------------
commande = Data(
    "Commande (produits, quantités, prénom, téléphone, repère)",
    classification=Classification.SENSITIVE,
    isPII=True,
    isStored=True,
)
jeton_suivi = Data("Jeton de suivi (128 bits)", classification=Classification.SENSITIVE)
session = Data(
    "Cookie de session JWT staff",
    classification=Classification.SECRET,
    isCredentials=True,
)
texte_masque = Data(
    "Texte WhatsApp masqué (sans nom ni numéro)",
    classification=Classification.RESTRICTED,
)
secret_app = Data(
    "Secrets (base, OAuth, JWT, Gemini)",
    classification=Classification.SECRET,
    isCredentials=True,
)
image = Data("Image Docker signée + SBOM", classification=Classification.PUBLIC)


def flow(src, dst, name, data, protocol="HTTPS", tls=TLSVersion.TLSv12, note=""):
    f = Dataflow(src, dst, name)
    f.protocol = protocol
    f.data = data
    f.tlsVersion = tls
    f.note = note
    return f


# --- Flux (numérotés dans l'ordre d'une soirée type) -------------------------
flow(client, web, "Commande depuis la PWA", commande)
flow(web, api, "POST /orders (appel authentifié par IAM)", commande)
flow(api, db, "Écriture commande (SQL paramétré)", commande, protocol="PostgreSQL/TLS")
flow(client, whatsapp, "Message prérempli", commande, note="Envoyé par le téléphone du client")
flow(client, web, "Suivi en direct (jeton dans le fragment #)", jeton_suivi)
flow(staff, web, "Connexion « Google »", session)
flow(api, oauth, "OIDC (code + PKCE)", session)
flow(staff, web, "Caisse, statuts, pilotage (cookie JWT)", session)
flow(web, api, "Requêtes staff + contrôle du rôle", session)
flow(api, gemini, "Assistant de commande", texte_masque)
flow(secrets, api, "Secrets injectés au démarrage", secret_app, protocol="Google API")
flow(dev, ci, "Pull request", image, protocol="Git/HTTPS")
flow(ci, api, "Déploiement par OIDC (sans clé)", image, protocol="Google API")

if __name__ == "__main__":
    tm.process()
