#!/usr/bin/env bash
# Relie un domaine au web de production (ADR 0012) : snackindb.com et www.snackindb.com.
#
#   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/setup-domain.sh snackindb.com
#
# Prérequis : le domaine est vérifié pour ce compte Google (Search Console, enregistrement TXT).
# Le script crée les liaisons Cloud Run, puis affiche les enregistrements DNS à créer chez le
# registrar, en « DNS only » (sans proxy) : Google doit voir le trafic pour émettre le certificat.
# Rejouable : une liaison existante est conservée.
set -euo pipefail

DOMAIN="${1:?Usage : $0 <domaine>}"
[[ "$DOMAIN" =~ ^[a-z0-9-]+(\.[a-z0-9-]+)+$ ]] || { echo "Domaine invalide : ${DOMAIN}" >&2; exit 2; }
PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
REGION="${GCP_REGION:-us-central1}"
SERVICE="snacki-web-prod"
GCLOUD=(--project "$PROJECT" --region "$REGION" --quiet)

if ! gcloud domains list-user-verified --format 'value(id)' | grep -qx "$DOMAIN"; then
  echo "Domaine non vérifié. Lancez : gcloud domains verify ${DOMAIN}" >&2
  echo "puis ajoutez chez le registrar l'enregistrement TXT proposé par Search Console." >&2
  exit 1
fi

for host in "$DOMAIN" "www.${DOMAIN}"; do
  if gcloud beta run domain-mappings describe --domain "$host" "${GCLOUD[@]}" >/dev/null 2>&1; then
    echo "Liaison déjà présente : ${host}"
  else
    gcloud beta run domain-mappings create --service "$SERVICE" --domain "$host" "${GCLOUD[@]}"
  fi
done

echo
echo "Enregistrements DNS à créer chez le registrar (DNS only, sans proxy) :"
for host in "$DOMAIN" "www.${DOMAIN}"; do
  gcloud beta run domain-mappings describe --domain "$host" "${GCLOUD[@]}" \
    --format "table[box,title='${host}'](status.resourceRecords.type,status.resourceRecords.rrdata)"
done
echo
echo "Ensuite : variable GitHub PUBLIC_URL_PROD=https://${DOMAIN}, adresse de retour OAuth"
echo "https://${DOMAIN}/auth/callback, puis un déploiement. Voir docs/adr/0012-domaine.md."
