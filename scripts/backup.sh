#!/usr/bin/env bash
# Sauvegarde des bases HealthAI Coach (MariaDB + MongoDB) depuis les conteneurs Docker.
# Usage : bash scripts/backup.sh   (les conteneurs doivent tourner)
# Sortie : backups/AAAAMMJJ_HHMMSS/
set -euo pipefail
cd "$(dirname "$0")/.."

DB_CONTAINER="${DB_CONTAINER:-healthai-db}"
MONGO_CONTAINER="${MONGO_CONTAINER:-healthai-mongo}"
DB_NAME="${DB_NAME:-healthai_coaching}"
DB_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root}"
MONGO_DB="${MONGO_DB_NAME:-healthai_nosql}"

TS="$(date +%Y%m%d_%H%M%S)"
OUT="backups/$TS"
mkdir -p "$OUT"

echo "==> Sauvegarde MariaDB ($DB_NAME) depuis $DB_CONTAINER ..."
docker exec "$DB_CONTAINER" mariadb-dump -uroot -p"$DB_ROOT_PASSWORD" \
  --single-transaction --routines --triggers "$DB_NAME" > "$OUT/mariadb_${DB_NAME}.sql"

echo "==> Sauvegarde MongoDB ($MONGO_DB) depuis $MONGO_CONTAINER ..."
docker exec "$MONGO_CONTAINER" mongodump --quiet --db "$MONGO_DB" --archive > "$OUT/mongo_${MONGO_DB}.archive"

echo "==> Sauvegarde terminée : $OUT"
ls -lh "$OUT"
