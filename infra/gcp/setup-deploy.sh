#!/usr/bin/env bash
# Prépare Google Cloud et GitHub pour le déploiement continu de Snacki (J5, ADR 0007).
# À lancer une fois, depuis un poste connecté (gcloud auth login, gh auth login). Relançable.
#
#   ./infra/gcp/setup-deploy.sh <id-du-projet-gcp> <propriétaire/dépôt>
#   ./infra/gcp/setup-deploy.sh snacki-ndb-2026 Mu7ammad01/Snacki.ndb
#
# Ce que le script crée :
#   - le registre d'images (Artifact Registry), nettoyé automatiquement ;
#   - 5 comptes de service sans aucun rôle sur le projet : le déployeur (utilisé par GitHub)
#     et un compte par service et par environnement (api et web, staging et prod) ;
#   - les 2 secrets « URL de la base » (staging, prod), lisibles chacun par une seule API ;
#   - les 4 services Cloud Run (image d'attente) : API privée, web public, web autorisé à appeler l'API ;
#   - la fédération d'identité GitHub → Google (aucune clé), limitée à deploy.yml sur main ;
#   - côté GitHub : les variables du workflow et les environnements staging et production.
set -euo pipefail

PROJECT="${1:?Usage : $0 <id-du-projet-gcp> <propriétaire/dépôt>}"
REPO="${2:?Usage : $0 <id-du-projet-gcp> <propriétaire/dépôt>}"
REGION="us-central1"
REGISTRY="snacki"
POOL="github"
PROVIDER="github-actions"
DEPLOYER="snacki-deployer@${PROJECT}.iam.gserviceaccount.com"
PLACEHOLDER="us-docker.pkg.dev/cloudrun/container/hello"
HERE="$(cd "$(dirname "$0")" && pwd)"

# Jamais de question cachée : une commande gcloud qui voudrait demander « oui/non » échoue
# avec un message clair au lieu d'attendre une réponse invisible.
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
command -v gcloud >/dev/null || { echo "Installez Google Cloud CLI"; exit 1; }
command -v gh >/dev/null || { echo "Installez GitHub CLI"; exit 1; }
gcloud config set project "$PROJECT" >/dev/null
NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
# Identifiant numérique du dépôt : il ne change jamais, même si le dépôt est renommé ou si
# quelqu'un recrée plus tard un dépôt du même nom.
REPO_ID="$(gh api "repos/${REPO}" --jq .id)"
REPO="$(gh api "repos/${REPO}" --jq .full_name)"   # casse exacte, utilisée dans la condition

sa_email() { echo "$1@${PROJECT}.iam.gserviceaccount.com"; }

# Les droits IAM mettent parfois quelques secondes à voir un compte tout juste créé.
retry() { local i; for i in 1 2 3 4 5; do "$@" >/dev/null && return 0; sleep $((i * 3)); done; "$@" >/dev/null; }

echo "1/7 Registre d'images ${REGISTRY} (${REGION})"
if ! gcloud artifacts repositories describe "$REGISTRY" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REGISTRY" --location "$REGION" \
    --repository-format docker --description "Images Snacki (api, web)"
fi
# Les 3 dernières versions de chaque image sont gardées (retour arrière), le reste part après 7 jours :
# le registre reste sous les 0,5 Go gratuits.
gcloud artifacts repositories set-cleanup-policies "$REGISTRY" --location "$REGION" \
  --policy "${HERE}/ar-cleanup.json" --no-dry-run >/dev/null

echo "2/7 Comptes de service (aucun rôle sur le projet)"
for sa in snacki-deployer snacki-api-staging snacki-api-prod snacki-web-staging snacki-web-prod; do
  if ! gcloud iam service-accounts describe "$(sa_email "$sa")" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$sa" --display-name "$sa"
  fi
done

echo "3/7 Droits du déployeur : déployer, publier des images, utiliser les 4 comptes d'exécution"
retry gcloud projects add-iam-policy-binding "$PROJECT" --condition=None \
  --member "serviceAccount:${DEPLOYER}" --role roles/run.developer
retry gcloud artifacts repositories add-iam-policy-binding "$REGISTRY" --location "$REGION" \
  --member "serviceAccount:${DEPLOYER}" --role roles/artifactregistry.writer
for sa in snacki-api-staging snacki-api-prod snacki-web-staging snacki-web-prod; do
  retry gcloud iam service-accounts add-iam-policy-binding "$(sa_email "$sa")" \
    --member "serviceAccount:${DEPLOYER}" --role roles/iam.serviceAccountUser
done

echo "4/7 Secrets : URL de la base Neon, une par environnement"
for env in staging prod; do
  secret="snacki-db-url-${env}"
  if ! gcloud secrets describe "$secret" >/dev/null 2>&1; then
    gcloud secrets create "$secret" --replication-policy automatic --labels "app=snacki,env=${env}"
  fi
  if [ -z "$(gcloud secrets versions list "$secret" --filter 'state=ENABLED' --format 'value(name)' --limit 1)" ]; then
    # Saisie masquée : l'URL n'apparaît ni à l'écran, ni dans l'historique, ni dans un fichier.
    read -rsp "    Colle l'URL Neon de la branche ${env} (rien ne s'affiche), puis Entrée : " url; echo
    case "$url" in
      postgresql://*sslmode=require*|postgres://*sslmode=require*) ;;
      *) unset url; echo "    URL refusée : postgresql://… avec sslmode=require attendu"; exit 1 ;;
    esac
    printf '%s' "$url" | gcloud secrets versions add "$secret" --data-file=- >/dev/null
    unset url
    echo "    version 1 enregistrée"
  else
    echo "    ${secret} : déjà renseigné"
  fi
  # Seule l'API de cet environnement peut lire ce secret (T22).
  retry gcloud secrets add-iam-policy-binding "$secret" \
    --member "serviceAccount:$(sa_email "snacki-api-${env}")" --role roles/secretmanager.secretAccessor
done

echo "5/7 Services Cloud Run (image d'attente, remplacée au premier déploiement)"
for env in staging prod; do
  api="snacki-api-${env}"; web="snacki-web-${env}"
  if ! gcloud run services describe "$api" --region "$REGION" >/dev/null 2>&1; then
    gcloud run deploy "$api" --region "$REGION" --image "$PLACEHOLDER" --quiet \
      --service-account "$(sa_email "$api")" --no-allow-unauthenticated --max-instances 1
  fi
  if ! gcloud run services describe "$web" --region "$REGION" >/dev/null 2>&1; then
    gcloud run deploy "$web" --region "$REGION" --image "$PLACEHOLDER" --quiet \
      --service-account "$(sa_email "$web")" --allow-unauthenticated --max-instances 1
  fi
  # L'API est privée : seul le compte du serveur web de CET environnement peut l'appeler.
  retry gcloud run services add-iam-policy-binding "$api" --region "$REGION" \
    --member "serviceAccount:$(sa_email "$web")" --role roles/run.invoker
done

echo "6/7 Fédération d'identité GitHub → Google (aucune clé stockée, T21)"
if ! gcloud iam workload-identity-pools describe "$POOL" --location global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL" --location global --display-name "GitHub Actions"
fi
# Seul le workflow deploy.yml de CE dépôt, sur main, peut obtenir un accès. Un autre dépôt,
# une autre branche, une PR ou un autre workflow reçoivent un refus de Google.
CONDITION="assertion.repository_id == '${REPO_ID}' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref.startsWith('${REPO}/.github/workflows/deploy.yml@')"
MAPPING="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref"
if gcloud iam workload-identity-pools providers describe "$PROVIDER" --location global \
     --workload-identity-pool "$POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER" --location global \
    --workload-identity-pool "$POOL" --attribute-mapping "$MAPPING" --attribute-condition "$CONDITION" >/dev/null
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location global \
    --workload-identity-pool "$POOL" --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "$MAPPING" --attribute-condition "$CONDITION"
fi
retry gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER" --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository_id/${REPO_ID}"

echo "7/7 Journaux gardés 30 jours (les adresses IP sont des données personnelles), GitHub"
gcloud logging buckets update _Default --location global --retention-days 30 >/dev/null
# Ce ne sont pas des secrets : sans le jeton OIDC signé par GitHub pour ce dépôt, ces noms ne
# donnent accès à rien.
gh variable set GCP_PROJECT_ID --repo "$REPO" --body "$PROJECT"
gh variable set GCP_REGION --repo "$REPO" --body "$REGION"
gh variable set GCP_DEPLOYER_SA --repo "$REPO" --body "$DEPLOYER"
gh variable set GCP_WIF_PROVIDER --repo "$REPO" \
  --body "projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
# Environnements : déploiement depuis main uniquement ; la production attend ton approbation.
ME="$(gh api user --jq .id)"
printf '{"deployment_branch_policy":{"protected_branches":true,"custom_branch_policies":false}}' |
  gh api -X PUT "repos/${REPO}/environments/staging" --input - >/dev/null
printf '{"reviewers":[{"type":"User","id":%s}],"deployment_branch_policy":{"protected_branches":true,"custom_branch_policies":false}}' "$ME" |
  gh api -X PUT "repos/${REPO}/environments/production" --input - >/dev/null \
  || echo "    Avertissement : approbation non disponible pour ce dépôt (dépôt privé sans offre payante)."

echo
echo "Terminé. Vérification :"
gcloud run services list --region "$REGION" --format 'table(metadata.name,status.url)'
gh variable list --repo "$REPO"
gh api "repos/${REPO}/environments" --jq '.environments[] | "\(.name) : \([.protection_rules[].type] | join(", "))"'
