#!/usr/bin/env bash
# Prépare le test de restauration mensuel dans GitHub Actions (ADR 0013, complément J10).
#
#   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/setup-restore-ci.sh Mu7ammad01/Snacki.ndb
#
# Moindre privilège :
#   - compte snacki-restore-test : LIT les sauvegardes (ni écriture, ni effacement, ni base) ;
#   - pool d'identité « github-restore », séparé de celui du déploiement : un jeton de ce
#     workflow ne peut pas obtenir le compte de déploiement, et inversement ;
#   - Google n'accepte que .github/workflows/restore-test.yml, sur main, dans CE dépôt.
# Rejouable. Ne touche ni au déploiement, ni à la base, ni aux sauvegardes.
set -euo pipefail

REPO="${1:?Usage : $0 <propriétaire/dépôt>}"
PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
BUCKET="${PROJECT}-backups"
SA_NAME="snacki-restore-test"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
POOL="github-restore"
PROVIDER="restore-test"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
command -v gh >/dev/null || { echo "Installez GitHub CLI" >&2; exit 1; }
retry() { local i; for i in 1 2 3 4 5; do "$@" >/dev/null 2>&1 && return 0; sleep $((i * 3)); done; "$@" >/dev/null; }

NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
REPO_ID="$(gh api "repos/${REPO}" --jq .id)"
REPO="$(gh api "repos/${REPO}" --jq .full_name)"

echo "1/4 Compte ${SA_NAME} (lecture des sauvegardes seulement)"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" --display-name "$SA_NAME"
fi
retry gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project "$PROJECT" \
  --member "serviceAccount:${SA}" --role roles/storage.objectViewer

echo "2/4 Pool d'identité ${POOL} (séparé du déploiement)"
if ! gcloud iam workload-identity-pools describe "$POOL" --project "$PROJECT" --location global \
  >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL" --project "$PROJECT" --location global \
    --display-name "GitHub restore test"
fi
CONDITION="assertion.repository_id == '${REPO_ID}' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref.startsWith('${REPO}/.github/workflows/restore-test.yml@')"
MAPPING="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id"
if gcloud iam workload-identity-pools providers describe "$PROVIDER" --project "$PROJECT" \
  --location global --workload-identity-pool "$POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER" --project "$PROJECT" \
    --location global --workload-identity-pool "$POOL" \
    --attribute-mapping "$MAPPING" --attribute-condition "$CONDITION" >/dev/null
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project "$PROJECT" \
    --location global --workload-identity-pool "$POOL" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "$MAPPING" --attribute-condition "$CONDITION" >/dev/null
fi

echo "3/4 Seul ce pool peut agir en tant que ${SA_NAME}"
retry gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository_id/${REPO_ID}"

echo "4/4 Variables GitHub"
gh variable set GCP_RESTORE_SA --repo "$REPO" --body "$SA"
gh variable set GCP_RESTORE_WIF_PROVIDER --repo "$REPO" \
  --body "projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "Prêt. Premier essai : GitHub → Actions → restore-test → Run workflow (branche main)."
