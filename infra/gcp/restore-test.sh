#!/usr/bin/env bash
# Test de restauration de la dernière sauvegarde (ADR 0013), une fois par mois. Ne touche pas la
# production : la copie est restaurée dans un PostgreSQL jetable (Docker), compté, puis effacé.
#
#   GCP_PROJECT=snacki-ndb-2026 ./infra/gcp/restore-test.sh
#
# Une sauvegarde qu'on n'a jamais restaurée n'est pas une sauvegarde.
set -euo pipefail

PROJECT="${GCP_PROJECT:?GCP_PROJECT manquant}"
BUCKET="${PROJECT}-backups"
NAME="snacki-restore"
PG_IMAGE="${PG_IMAGE:-postgres:17}"   # même version majeure que pg_dump, ou plus récente
WORK="$(mktemp -d)"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT   # la copie contient des données de clients : rien ne reste sur le disque

LATEST="$(gcloud storage ls "gs://${BUCKET}/prod/**" --project "$PROJECT" | sort | tail -n1)"
[ -n "$LATEST" ] || { echo "ÉCHEC : aucune sauvegarde dans gs://${BUCKET}" >&2; exit 1; }
STAMP="$(grep -oE '[0-9]{8}T[0-9]{6}Z' <<<"$LATEST")"
TAKEN="$(date -u -d "${STAMP:0:8} ${STAMP:9:2}:${STAMP:11:2}:${STAMP:13:2}" +%s)"
AGE_H=$(( ($(date -u +%s) - TAKEN) / 3600 ))
echo "Dernière sauvegarde : ${LATEST##*/} (il y a ${AGE_H} h)"
[ "$AGE_H" -le 26 ] || echo "ATTENTION : plus de 26 h, la sauvegarde de cette nuit manque"

gcloud storage cp "$LATEST" "${WORK}/snacki.dump" --project "$PROJECT" >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=restore-only "$PG_IMAGE" >/dev/null
for _ in $(seq 1 30); do docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
docker cp "${WORK}/snacki.dump" "${NAME}:/tmp/snacki.dump"
docker exec "$NAME" pg_restore --no-owner --no-privileges -U postgres -d postgres /tmp/snacki.dump

echo "Contenu restauré :"
docker exec "$NAME" psql -U postgres -At -F ' : ' -c "
  SELECT 'commandes', count(*) FROM orders
  UNION ALL SELECT 'ventes historiques', count(*) FROM history_sale
  UNION ALL SELECT 'cartes de fidélité', count(*) FROM loyalty_card
  UNION ALL SELECT 'comptes du staff', count(*) FROM staff_user
  UNION ALL SELECT 'version du schéma', (SELECT count(*) FROM alembic_version)" |
  sed 's/^/    /'
echo "Restauration réussie. Copie et conteneur effacés."
