#!/usr/bin/env bash
# Restauration RÉELLE d'une sauvegarde de production (procédure d'incident, docs/security/incident.md).
#
#   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/restore-to.sh [chemin gs://… d'une sauvegarde]
#
# Sans chemin : la plus récente. La copie est restaurée dans une base NEUVE et VIDE (nouvelle base
# ou branche Neon), dont l'URL est demandée dans une invite masquée. Refus si cette URL est celle
# de la production actuelle ou si la base cible contient déjà des tables. La production n'est
# basculée qu'ensuite, à la main, après vérification (étape 4 de la procédure).
set -euo pipefail

PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
BUCKET="${PROJECT}-backups"
PG_IMAGE="${PG_IMAGE:-postgres:18}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"; unset TARGET CURRENT PGURL' EXIT   # la copie contient des données de clients

DUMP="${1:-$(gcloud storage ls "gs://${BUCKET}/prod/**" --project "$PROJECT" | sort | tail -n1)}"
[[ "$DUMP" == "gs://${BUCKET}/prod/"*.dump ]] || { echo "Sauvegarde invalide : ${DUMP}" >&2; exit 2; }
echo "Sauvegarde choisie : ${DUMP##*/}"

read -rsp "URL de la base CIBLE (neuve, vide), invisible à la saisie : " TARGET
echo
TARGET="${TARGET//[[:space:]]/}"
[[ "$TARGET" == postgres*://*sslmode=require* ]] || { echo "URL PostgreSQL avec sslmode=require attendue" >&2; exit 2; }
CURRENT="$(gcloud secrets versions access latest --secret snacki-db-url-prod --project "$PROJECT")"
[ "$TARGET" != "$CURRENT" ] || { echo "REFUS : c'est la base de production actuelle" >&2; exit 1; }

# L'URL passe par l'environnement (-e PGURL sans valeur), jamais sur une ligne de commande visible.
export PGURL="$TARGET"
psql_t() { docker run --rm -e PGURL "$PG_IMAGE" sh -c 'psql "$PGURL" -At -c "$0"' "$1"; }
TABLES="$(psql_t "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
[ "$TABLES" = "0" ] || { echo "REFUS : la base cible contient déjà ${TABLES} table(s)" >&2; exit 1; }

gcloud storage cp "$DUMP" "${WORK}/snacki.dump" --project "$PROJECT" >/dev/null
docker run --rm -e PGURL -v "${WORK}:/w:ro" "$PG_IMAGE" \
  sh -c 'pg_restore --exit-on-error --no-owner --no-privileges -d "$PGURL" /w/snacki.dump'

echo "Restauration terminée. Contenu :"
psql_t "SELECT 'commandes : ' || count(*) FROM orders UNION ALL
        SELECT 'ventes historiques : ' || count(*) FROM history_sale UNION ALL
        SELECT 'cartes de fidélité : ' || count(*) FROM loyalty_card UNION ALL
        SELECT 'comptes du staff : ' || count(*) FROM staff_user UNION ALL
        SELECT 'migration : ' || version_num FROM alembic_version" | sed 's/^/    /'
echo "Étape suivante (procédure d'incident, étape 4) : basculer snacki-db-url-prod vers cette base."
