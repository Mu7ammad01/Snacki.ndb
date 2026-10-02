#!/usr/bin/env bash
# Déploie une version de Snacki dans un environnement : migration de la base, API privée, web public,
# puis contrôles de fumée. Appelé par .github/workflows/deploy.yml (ADR 0007).
#
#   GCP_PROJECT=… ./infra/gcp/deploy.sh <staging|prod> <image-api@sha256:…> <image-web@sha256:…>
#
# Les images sont désignées par leur empreinte (sha256), jamais par une étiquette : staging et
# production reçoivent exactement les mêmes octets, ceux qui ont passé Trivy.
set -euo pipefail

ENV="${1:?Usage : $0 <staging|prod> <image-api> <image-web>}"
API_IMAGE="${2:?image api manquante}"
WEB_IMAGE="${3:?image web manquante}"
case "$ENV" in staging | prod) ;; *) echo "Environnement inconnu : ${ENV}" >&2; exit 2 ;; esac
for image in "$API_IMAGE" "$WEB_IMAGE"; do
  [[ "$image" == *@sha256:* ]] || { echo "Image sans empreinte refusée : ${image}" >&2; exit 2; }
done

PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
REGION="${GCP_REGION:-us-central1}"
API="snacki-api-${ENV}"
WEB="snacki-web-${ENV}"
SA_API="${API}@${PROJECT}.iam.gserviceaccount.com"
SA_WEB="${WEB}@${PROJECT}.iam.gserviceaccount.com"
DB_SECRET="SNACKI_DATABASE_URL=snacki-db-url-${ENV}:latest"
GCLOUD=(--project "$PROJECT" --region "$REGION" --quiet)
# Garde-fous de coût (T23) : jamais plus de 2 instances, zéro instance au repos.
LIMITS=(--min-instances 0 --max-instances 2 --cpu 1 --memory 512Mi --concurrency 40 --timeout 30s)

fail() { echo "ÉCHEC : $*" >&2; exit 1; }

echo "1/4 Migration de la base (${ENV}) : Cloud Run Job, avant la nouvelle version de l'API"
gcloud run jobs deploy "snacki-migrate-${ENV}" "${GCLOUD[@]}" --image "$API_IMAGE" \
  --service-account "$SA_API" --set-secrets "$DB_SECRET" --set-env-vars "SNACKI_ENVIRONMENT=${ENV}" \
  --command alembic --args upgrade,head --max-retries 0 --task-timeout 300s \
  --labels "app=snacki,env=${ENV}" --execute-now --wait

echo "2/4 API (${ENV}) : privée, n'accepte que le jeton du serveur web"
# Pas d'option --allow-unauthenticated : les droits posés par setup-deploy.sh sont conservés.
gcloud run deploy "$API" "${GCLOUD[@]}" --image "$API_IMAGE" --service-account "$SA_API" \
  --set-secrets "$DB_SECRET" \
  --set-env-vars "SNACKI_ENVIRONMENT=${ENV},SNACKI_TRUST_FORWARDED_FOR=true" \
  --labels "app=snacki,env=${ENV}" "${LIMITS[@]}"
API_URL="$(gcloud run services describe "$API" "${GCLOUD[@]}" --format 'value(status.url)')"

echo "3/4 Web (${ENV}) : public, appelle l'API avec son jeton d'identité"
gcloud run deploy "$WEB" "${GCLOUD[@]}" --image "$WEB_IMAGE" --service-account "$SA_WEB" \
  --set-env-vars "SNACKI_API_URL=${API_URL},SNACKI_API_AUTH=gcp" \
  --labels "app=snacki,env=${ENV}" "${LIMITS[@]}"
WEB_URL="$(gcloud run services describe "$WEB" "${GCLOUD[@]}" --format 'value(status.url)')"

echo "4/4 Contrôles de fumée"
# Cloud Run réserve certains chemins finissant par « z » (/healthz) : on teste /v1/menu.
code="$(curl -s -o /dev/null -w '%{http_code}' "${API_URL}/v1/menu")"
[ "$code" = "403" ] || fail "l'API répond ${code} sans jeton : elle doit être privée (403)"
echo "    API sans jeton : 403 (privée)"

headers="$(curl -fsS -D - -o /dev/null "${WEB_URL}/")" || fail "le web ne répond pas"
grep -qi "^content-security-policy:.*'nonce-" <<<"$headers" || fail "CSP à nonce absente"
grep -qi '^strict-transport-security: max-age=31536000' <<<"$headers" || fail "HSTS absent"
echo "    web : 200, CSP à nonce, HSTS"

# Le nom du produit vient de la base : s'il est dans la page, la chaîne web → API → Neon fonctionne.
curl -fsS "${WEB_URL}/" | grep -q 'Salade de fruits' || fail "menu absent : le web n'atteint pas l'API"
echo "    menu lu dans la base, via l'API privée"

echo "Version déployée en ${ENV} : ${WEB_URL}"
if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "web_url=${WEB_URL}" >>"$GITHUB_OUTPUT"; fi
