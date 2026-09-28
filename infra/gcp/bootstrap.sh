#!/usr/bin/env bash
# Crée le projet Google Cloud de Snacki, active les API utiles et pose une alerte de budget à 1.
#
#   ./infra/gcp/bootstrap.sh <id-du-projet> <id-du-compte-de-facturation>
#
# Exemple : ./infra/gcp/bootstrap.sh snacki-ndb-2026 0X0X0X-0X0X0X-0X0X0X
# Trouver l'identifiant du compte de facturation : gcloud billing accounts list
#
# Prérequis : gcloud connecté (`gcloud auth login`) avec les droits de créer un projet
# et d'administrer le compte de facturation. Relançable sans effet de bord.
#
# Important : une alerte de budget PRÉVIENT par e-mail, elle ne coupe rien. Les autres garde-fous
# (max-instances=2, quotas IA, limites de débit) arrivent avec le déploiement (J5).
set -euo pipefail

PROJECT_ID="${1:?Usage : $0 <id-du-projet> <id-du-compte-de-facturation>}"
BILLING_ACCOUNT="${2:?Usage : $0 <id-du-projet> <id-du-compte-de-facturation>}"
REGION="us-central1"          # région des offres gratuites de Cloud Run
BUDGET_NAME="snacki-garde-fou"

command -v gcloud >/dev/null || { echo "Installez Google Cloud CLI : https://cloud.google.com/sdk"; exit 1; }

echo "1/5 Projet ${PROJECT_ID}"
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "    existe déjà"
else
  gcloud projects create "$PROJECT_ID" --name="Snacki" --labels=app=snacki,env=prod
fi
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud config set run/region "$REGION" >/dev/null

echo "2/5 Facturation (nécessaire pour Cloud Run, même dans l'offre gratuite)"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT" >/dev/null

echo "3/5 API utilisées par le plan (J1 à J15)"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com \
  billingbudgets.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --project "$PROJECT_ID"

echo "4/5 Alerte de budget à 1 (dans la devise du compte de facturation)"
CURRENCY="$(gcloud billing accounts describe "$BILLING_ACCOUNT" --format='value(currencyCode)')"
CURRENCY="${CURRENCY:-EUR}"
if gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" \
     --format='value(displayName)' | grep -qx "$BUDGET_NAME"; then
  echo "    budget ${BUDGET_NAME} déjà présent"
else
  # Alertes à 50 %, 90 % et 100 % de la dépense réelle, et à 100 % de la dépense prévue.
  gcloud billing budgets create \
    --billing-account="$BILLING_ACCOUNT" \
    --display-name="$BUDGET_NAME" \
    --budget-amount="1.00${CURRENCY}" \
    --filter-projects="projects/${PROJECT_ID}" \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0 \
    --threshold-rule=percent=1.0,basis=forecasted-spend
fi

echo "5/5 Résumé"
gcloud projects describe "$PROJECT_ID" --format='table(projectId,name,lifecycleState)'
gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" \
  --format='table(displayName,amount.specifiedAmount.units,amount.specifiedAmount.currencyCode)'
echo
echo "À faire à la main (5 minutes) :"
echo "  - activer la validation en deux étapes sur le compte Google qui administre le projet ;"
echo "  - vérifier que l'e-mail d'alerte de budget arrive bien (Facturation > Budgets et alertes)."
