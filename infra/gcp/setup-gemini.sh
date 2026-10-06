#!/usr/bin/env bash
# Range la clé de l'API Gemini dans Secret Manager pour un environnement (J9, ADR 0014).
#
#   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/setup-gemini.sh <staging|prod>
#
# La clé est demandée dans une invite masquée : elle n'apparaît ni à l'écran, ni dans
# l'historique du shell, ni dans un fichier. Seule l'API de cet environnement peut la lire.
# Ensuite : variable GitHub GEMINI_ENABLED_STAGING (ou _PROD) = true, puis un déploiement.
set -euo pipefail

ENV="${1:?Usage : $0 <staging|prod>}"
case "$ENV" in staging | prod) ;; *) echo "Environnement inconnu : ${ENV}" >&2; exit 2 ;; esac
PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
SECRET="snacki-gemini-key-${ENV}"
SA="snacki-api-${ENV}@${PROJECT}.iam.gserviceaccount.com"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

read -rsp "Clé API Gemini (${ENV}), invisible à la saisie : " KEY
echo
KEY="${KEY//[[:space:]]/}"  # espaces ou retour à la ligne collés par erreur
[[ "$KEY" =~ ^[A-Za-z0-9._-]{20,200}$ ]] || { echo "Format de clé inattendu : rien n'est enregistré" >&2; exit 1; }

if ! gcloud secrets describe "$SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud secrets create "$SECRET" --project "$PROJECT" --replication-policy automatic >/dev/null
fi
printf '%s' "$KEY" | gcloud secrets versions add "$SECRET" --project "$PROJECT" --data-file=- >/dev/null
unset KEY
gcloud secrets add-iam-policy-binding "$SECRET" --project "$PROJECT" \
  --member "serviceAccount:${SA}" --role roles/secretmanager.secretAccessor >/dev/null
echo "Clé enregistrée dans ${SECRET}, lisible par ${SA} seulement."
echo "Étape suivante : variable GitHub GEMINI_ENABLED_$(tr '[:lower:]' '[:upper:]' <<<"$ENV")=true, puis déployer."
