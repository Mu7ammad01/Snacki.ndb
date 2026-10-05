#!/usr/bin/env bash
# Met en place la sauvegarde nocturne de la base de production (ADR 0013). Relançable.
#
#   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/setup-backup.sh [adresse-mail-des-alertes]
#
# À lancer APRÈS le déploiement de la version qui contient pg_dump dans l'image de l'API.
# Ce que le script crée :
#   - le bucket <projet>-backups : privé, conservation 30 jours (aucune copie effaçable avant),
#     effacement automatique après 31 jours ;
#   - le compte snacki-backup-prod : lit l'URL de la base de production, crée des objets dans le
#     bucket (ni lecture ni effacement) ;
#   - la tâche Cloud Run snacki-backup-prod (image actuelle de l'API de production) ;
#   - le compte snacki-scheduler et la planification chaque nuit à 3 h (heure de Nouadhibou) ;
#   - une alerte par e-mail si une sauvegarde échoue ;
# puis lance une première sauvegarde et l'affiche.
set -euo pipefail

PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
REGION="${GCP_REGION:-us-central1}"
EMAIL="${1:-$(gcloud config get-value account 2>/dev/null)}"
BUCKET="${PROJECT}-backups"
JOB="snacki-backup-prod"
SA="snacki-backup-prod@${PROJECT}.iam.gserviceaccount.com"
SCHED="snacki-scheduler@${PROJECT}.iam.gserviceaccount.com"
DEPLOYER="snacki-deployer@${PROJECT}.iam.gserviceaccount.com"
GCLOUD=(--project "$PROJECT" --region "$REGION" --quiet)
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
[[ "$EMAIL" == *@*.* ]] || { echo "Adresse e-mail des alertes manquante" >&2; exit 2; }
retry() { local i; for i in 1 2 3 4 5; do "$@" >/dev/null 2>&1 && return 0; sleep $((i * 3)); done; "$@" >/dev/null; }

echo "1/7 Services Google Cloud"
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com monitoring.googleapis.com \
  storage.googleapis.com --project "$PROJECT"

echo "2/7 Bucket gs://${BUCKET} (privé, 30 jours de conservation)"
if ! gcloud storage buckets describe "gs://${BUCKET}" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention --default-storage-class STANDARD
fi
LIFECYCLE="$(mktemp)"
trap 'rm -f "$LIFECYCLE" "${POLICY:-}"' EXIT
printf '{"rule":[{"action":{"type":"Delete"},"condition":{"age":31}}]}' >"$LIFECYCLE"
gcloud storage buckets update "gs://${BUCKET}" --project "$PROJECT" \
  --retention-period 30d --lifecycle-file "$LIFECYCLE" >/dev/null

echo "3/7 Comptes de service"
for name in snacki-backup-prod snacki-scheduler; do
  if ! gcloud iam service-accounts describe "${name}@${PROJECT}.iam.gserviceaccount.com" \
    --project "$PROJECT" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --project "$PROJECT" --display-name "$name"
  fi
done
retry gcloud secrets add-iam-policy-binding snacki-db-url-prod --project "$PROJECT" \
  --member "serviceAccount:${SA}" --role roles/secretmanager.secretAccessor
retry gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project "$PROJECT" \
  --member "serviceAccount:${SA}" --role roles/storage.objectCreator
# Le déploiement continu met à jour l'image de la tâche : il doit pouvoir « agir en tant que » ce compte.
retry gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
  --member "serviceAccount:${DEPLOYER}" --role roles/iam.serviceAccountUser

echo "4/7 Tâche Cloud Run ${JOB}"
IMAGE="$(gcloud run services describe snacki-api-prod "${GCLOUD[@]}" \
  --format 'value(spec.template.spec.containers[0].image)')"
gcloud run jobs deploy "$JOB" "${GCLOUD[@]}" --image "$IMAGE" --service-account "$SA" \
  --set-secrets "SNACKI_DATABASE_URL=snacki-db-url-prod:latest" \
  --set-env-vars "SNACKI_ENVIRONMENT=prod,SNACKI_BACKUP_BUCKET=${BUCKET}" \
  --command python --args=-m,snacki_api.manage,backup \
  --max-retries 1 --task-timeout 900s --cpu 1 --memory 1Gi --labels "app=snacki,env=prod"
retry gcloud run jobs add-iam-policy-binding "$JOB" "${GCLOUD[@]}" \
  --member "serviceAccount:${SCHED}" --role roles/run.invoker

echo "5/7 Planification : chaque nuit à 3 h (Africa/Nouakchott)"
URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run"
SCHEDULE=(--location "$REGION" --project "$PROJECT" --schedule "0 3 * * *"
  --time-zone "Africa/Nouakchott" --uri "$URI" --http-method POST
  --oauth-service-account-email "$SCHED"
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform")
if gcloud scheduler jobs describe snacki-backup-nightly --location "$REGION" --project "$PROJECT" \
  >/dev/null 2>&1; then
  gcloud scheduler jobs update http snacki-backup-nightly "${SCHEDULE[@]}" >/dev/null
else
  gcloud scheduler jobs create http snacki-backup-nightly "${SCHEDULE[@]}" >/dev/null
fi

echo "6/7 Alerte par e-mail si une sauvegarde échoue (${EMAIL})"
CHANNEL="$(gcloud beta monitoring channels list --project "$PROJECT" \
  --filter "type=email AND labels.email_address=${EMAIL}" --format 'value(name)' | head -n1)"
if [ -z "$CHANNEL" ]; then
  CHANNEL="$(gcloud beta monitoring channels create --project "$PROJECT" --type email \
    --display-name "Snacki alertes" --channel-labels "email_address=${EMAIL}" --format 'value(name)')"
fi
TITLE="Snacki · sauvegarde nocturne en échec"
if [ -z "$(gcloud alpha monitoring policies list --project "$PROJECT" \
  --filter "displayName=\"${TITLE}\"" --format 'value(name)')" ]; then
  POLICY="$(mktemp)"
  cat >"$POLICY" <<JSON
{
  "displayName": "${TITLE}",
  "combiner": "OR",
  "conditions": [{
    "displayName": "Exécution de ${JOB} en échec",
    "conditionThreshold": {
      "filter": "resource.type = \"cloud_run_job\" AND resource.labels.job_name = \"${JOB}\" AND metric.type = \"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result = \"failed\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "0s",
      "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_DELTA"}]
    }
  }],
  "notificationChannels": ["${CHANNEL}"],
  "alertStrategy": {"autoClose": "86400s"}
}
JSON
  gcloud alpha monitoring policies create --project "$PROJECT" --policy-from-file "$POLICY" >/dev/null
fi

echo "7/7 Première sauvegarde (1 à 3 minutes)"
gcloud run jobs execute "$JOB" "${GCLOUD[@]}" --wait
gcloud storage ls -l "gs://${BUCKET}/prod/**" | tail -n 3
echo "Sauvegarde nocturne en place. Test de restauration : ./infra/gcp/restore-test.sh"
