#!/usr/bin/env bash
# Prépare la connexion du staff (J6, ADR 0008). À lancer une fois, après avoir créé les deux
# clients OAuth « Application Web » dans la console Google (un pour staging, un pour prod).
#
#   ./infra/gcp/setup-auth.sh <id-du-projet-gcp> <propriétaire/dépôt>
#
# Ce que le script crée, pour chaque environnement :
#   - snacki-oauth-secret-<env> : le secret du client OAuth, saisi en masqué ;
#   - snacki-session-key-<env>  : 48 octets aléatoires tirés ici, que personne ne voit ;
#   chacun lisible par la seule API de son environnement (T22).
# Côté GitHub : les identifiants des clients OAuth (publics) et l'adresse du premier admin.
set -euo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1  # jamais de question cachée

PROJECT="${1:?Usage : $0 <id-du-projet-gcp> <propriétaire/dépôt>}"
REPO="${2:?Usage : $0 <id-du-projet-gcp> <propriétaire/dépôt>}"
gcloud config set project "$PROJECT" >/dev/null
echo "Projet : $(gcloud projects describe "$PROJECT" --format='value(name)') (${PROJECT})"

sa_email() { echo "$1@${PROJECT}.iam.gserviceaccount.com"; }
retry() { local i; for i in 1 2 3 4 5; do "$@" >/dev/null && return 0; sleep $((i * 3)); done; "$@" >/dev/null; }

new_secret() {  # crée le secret s'il n'existe pas ; renvoie 0 s'il n'a encore aucune version
  local name="$1" env="$2"
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    gcloud secrets create "$name" --replication-policy automatic --labels "app=snacki,env=${env}" >/dev/null
  fi
  [ -z "$(gcloud secrets versions list "$name" --filter 'state=ENABLED' --format 'value(name)' --limit 1)" ]
}

for env in staging prod; do
  echo "== ${env}"
  api_sa="$(sa_email "snacki-api-${env}")"

  read -rp "    Identifiant du client OAuth ${env} (…apps.googleusercontent.com) : " client_id
  [[ "$client_id" =~ ^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$ ]] \
    || { echo "    Identifiant refusé (format …apps.googleusercontent.com attendu)"; exit 1; }
  var="OAUTH_CLIENT_ID_$(echo "$env" | tr '[:lower:]' '[:upper:]')"
  gh variable set "$var" --repo "$REPO" --body "$client_id" >/dev/null
  echo "    ${var} enregistré dans GitHub"

  secret="snacki-oauth-secret-${env}"
  if new_secret "$secret" "$env"; then
    # Saisie masquée, comme pour l'URL de la base : rien à l'écran, rien dans l'historique.
    read -rsp "    Colle le secret du client OAuth ${env} (rien ne s'affiche), puis Entrée : " value; echo
    [[ "$value" =~ ^GOCSPX-[A-Za-z0-9_-]{20,}$ ]] || { unset value; echo "    Secret refusé (GOCSPX-… attendu)"; exit 1; }
    printf '%s' "$value" | gcloud secrets versions add "$secret" --data-file=- >/dev/null
    unset value
    echo "    ${secret} : version 1 enregistrée"
  else
    echo "    ${secret} : déjà renseigné"
  fi

  key="snacki-session-key-${env}"
  if new_secret "$key" "$env"; then
    # La clé de session est tirée au hasard ici et va directement dans Secret Manager.
    head -c 48 /dev/urandom | base64 | tr -d '\n' | gcloud secrets versions add "$key" --data-file=- >/dev/null
    echo "    ${key} : clé aléatoire enregistrée"
  else
    echo "    ${key} : déjà présente"
  fi

  for s in "$secret" "$key"; do
    retry gcloud secrets add-iam-policy-binding "$s" \
      --member "serviceAccount:${api_sa}" --role roles/secretmanager.secretAccessor
  done
done

read -rp "Adresse Google du premier administrateur : " admin
[[ "$admin" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[a-zA-Z]{2,}$ ]] || { echo "Adresse refusée"; exit 1; }
gh variable set SNACKI_ADMIN_EMAIL --repo "$REPO" --body "$(echo "$admin" | tr '[:upper:]' '[:lower:]')" >/dev/null

echo
echo "Terminé. Vérification :"
for env in staging prod; do
  for s in "snacki-oauth-secret-${env}" "snacki-session-key-${env}"; do
    echo "  ${s} → $(gcloud secrets get-iam-policy "$s" --format 'value(bindings.members)')"
  done
done
gh variable list --repo "$REPO" | grep -E "^(OAUTH_CLIENT_ID|SNACKI_ADMIN)" | cut -f1
