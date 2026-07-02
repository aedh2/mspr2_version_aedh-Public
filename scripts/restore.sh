#!/usr/bin/env bash
# Restauration des bases HealthAI Coach depuis un dossier de sauvegarde.
# Usage : bash scripts/restore.sh backups/AAAAMMJJ_HHMMSS   (les conteneurs doivent tourner)
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${1:-}"
if [ -z "$BACKUP_DIR" ]; then
  echo "Usage : $0 <dossier_de_sauvegarde>"
  echo "Ex.   : $0 backups/20260702_120000"
  exit 1
fi
[ -d "$BACKUP_DIR" ] || { echo "Dossier introuvable : $BACKUP_DIR"; exit 1; }

DB_CONTAINER="${DB_CONTAINER:-healthai-db}"
MONGO_CONTAINER="${MONGO_CONTAINER:-healthai-mongo}"
DB_NAME="${DB_NAME:-healthai_coaching}"
DB_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root}"
MONGO_DB="${MONGO_DB_NAME:-healthai_nosql}"

SQL_FILE="$BACKUP_DIR/mariadb_${DB_NAME}.sql"
MONGO_FILE="$BACKUP_DIR/mongo_${MONGO_DB}.archive"

if [ -f "$SQL_FILE" ]; then
  echo "==> Restauration MariaDB ($DB_NAME) ..."
  docker exec -i "$DB_CONTAINER" mariadb -uroot -p"$DB_ROOT_PASSWORD" "$DB_NAME" < "$SQL_FILE"
else
  echo "!! Dump MariaDB absent ($SQL_FILE) — ignoré."
fi

if [ -f "$MONGO_FILE" ]; then
  echo "==> Restauration MongoDB ($MONGO_DB) ..."
  docker exec -i "$MONGO_CONTAINER" mongorestore --quiet --drop --archive < "$MONGO_FILE"
else
  echo "!! Archive MongoDB absente ($MONGO_FILE) — ignorée."
fi

echo "==> Restauration terminée depuis $BACKUP_DIR"
