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
OAUTH_CLIENT_ID="${OAUTH_CLIENT_ID:?OAUTH_CLIENT_ID manquant (variable GitHub, setup-auth.sh)}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
# Secrets lus par l'API au démarrage, depuis Secret Manager (jamais dans GitHub ni dans l'image).
SECRETS="SNACKI_DATABASE_URL=snacki-db-url-${ENV}:latest"
SECRETS+=",SNACKI_OAUTH_CLIENT_SECRET=snacki-oauth-secret-${ENV}:latest"
SECRETS+=",SNACKI_SESSION_SECRET=snacki-session-key-${ENV}:latest"
# Assistant IA (J9, ADR 0014) : clé Gemini seulement si la variable GitHub GEMINI_ENABLED_<ENV>
# vaut true (secret créé avant par setup-gemini.sh) ; sinon l'assistant fait l'analyse locale.
if [ "${GEMINI_ENABLED:-}" = true ]; then
  SECRETS+=",SNACKI_GEMINI_API_KEY=snacki-gemini-key-${ENV}:latest"
fi
GCLOUD=(--project "$PROJECT" --region "$REGION" --quiet)
# Garde-fous de coût (T23) : jamais plus de 2 instances, zéro instance au repos.
LIMITS=(--min-instances 0 --max-instances 2 --cpu 1 --memory 512Mi --concurrency 40 --timeout 30s)

fail() { echo "ÉCHEC : $*" >&2; exit 1; }

# Adresse publique du web : connue avant le déploiement (service créé par setup-deploy.sh). Elle
# fixe l'adresse de retour OAuth et l'origine acceptée par le web (jamais l'en-tête Host).
RUN_URL="$(gcloud run services describe "$WEB" "${GCLOUD[@]}" --format 'value(status.url)')"
# Domaine (ADR 0012) : PUBLIC_URL (variable GitHub PUBLIC_URL_PROD) remplace l'adresse run.app,
# qui reste active et redirige vers lui. Sans PUBLIC_URL (staging), l'adresse run.app sert.
WEB_URL="${PUBLIC_URL:-$RUN_URL}"
[[ "$WEB_URL" =~ ^https://[a-z0-9.-]+$ ]] || fail "PUBLIC_URL invalide : https://domaine, sans / final"
API_ENV="SNACKI_ENVIRONMENT=${ENV},SNACKI_OAUTH_CLIENT_ID=${OAUTH_CLIENT_ID}"
API_ENV+=",SNACKI_OAUTH_REDIRECT_URI=${WEB_URL}/auth/callback"

echo "1/4 Migration de la base (${ENV}) et premier admin : Cloud Run Job, avant la nouvelle API"
gcloud run jobs deploy "snacki-migrate-${ENV}" "${GCLOUD[@]}" --image "$API_IMAGE" \
  --service-account "$SA_API" --set-secrets "$SECRETS" \
  --set-env-vars "${API_ENV},SNACKI_BOOTSTRAP_ADMIN_EMAIL=${ADMIN_EMAIL}" \
  --command python --args=-m,snacki_api.manage,migrate --max-retries 0 --task-timeout 300s \
  --labels "app=snacki,env=${ENV}" --execute-now --wait

# Sauvegarde nocturne (ADR 0013) : la tâche est créée une fois par setup-backup.sh ; chaque
# déploiement lui donne la nouvelle image. Elle ne reçoit que l'URL de la base, aucun autre secret.
if [ "$ENV" = prod ] && gcloud run jobs describe snacki-backup-prod "${GCLOUD[@]}" >/dev/null 2>&1; then
  echo "    sauvegarde : tâche snacki-backup-prod mise à jour"
  gcloud run jobs update snacki-backup-prod "${GCLOUD[@]}" --image "$API_IMAGE" >/dev/null
fi

echo "2/4 API (${ENV}) : privée, n'accepte que le jeton du serveur web"
# Pas d'option --allow-unauthenticated : les droits posés par setup-deploy.sh sont conservés.
gcloud run deploy "$API" "${GCLOUD[@]}" --image "$API_IMAGE" --service-account "$SA_API" \
  --set-secrets "$SECRETS" \
  --set-env-vars "${API_ENV},SNACKI_TRUST_FORWARDED_FOR=true" \
  --labels "app=snacki,env=${ENV}" "${LIMITS[@]}"
API_URL="$(gcloud run services describe "$API" "${GCLOUD[@]}" --format 'value(status.url)')"

echo "3/4 Web (${ENV}) : public, appelle l'API avec son jeton d'identité"
gcloud run deploy "$WEB" "${GCLOUD[@]}" --image "$WEB_IMAGE" --service-account "$SA_WEB" \
  --set-env-vars "SNACKI_API_URL=${API_URL},SNACKI_API_AUTH=gcp,SNACKI_PUBLIC_URL=${WEB_URL}" \
  --labels "app=snacki,env=${ENV}" "${LIMITS[@]}"

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

# Espace staff : la page de connexion répond, l'espace lui-même renvoie vers la connexion.
code="$(curl -s -o /dev/null -w '%{http_code}' "${WEB_URL}/connexion")"
[ "$code" = "200" ] || fail "page de connexion du staff : ${code}"
where="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "${WEB_URL}/staff")"
[[ "$where" == 307*"/connexion" ]] || fail "l'espace staff doit renvoyer vers la connexion (${where})"
echo "    espace staff : fermé sans session"
where="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "${WEB_URL}/caisse")"
[[ "$where" == 307*"/connexion" ]] || fail "la caisse doit renvoyer vers la connexion (${where})"
code="$(curl -s -o /dev/null -w '%{http_code}' "${WEB_URL}/api/caisse/orders")"
[ "$code" = "401" ] || fail "commandes de la caisse sans session : ${code}"
echo "    caisse : fermée sans session"
where="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "${WEB_URL}/pilotage")"
[[ "$where" == 307*"/connexion" ]] || fail "le pilotage doit renvoyer vers la connexion (${where})"
echo "    pilotage : fermé sans session"
code="$(curl -s -o /dev/null -w '%{http_code}' "${WEB_URL}/carte")"
[ "$code" = "200" ] || fail "page de suivi de carte : ${code}"
echo "    carte de fidélité : page publique en ligne"
if [ "$WEB_URL" != "$RUN_URL" ]; then
  where="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "${RUN_URL}/carte")"
  [ "$where" = "308 ${WEB_URL}/carte" ] || fail "l'ancienne adresse doit renvoyer vers ${WEB_URL} (${where})"
  echo "    ancienne adresse run.app : 308 vers ${WEB_URL} (QR des cartes imprimées)"
fi

echo "Version déployée en ${ENV} : ${WEB_URL}"
if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "web_url=${WEB_URL}" >>"$GITHUB_OUTPUT"; fi
