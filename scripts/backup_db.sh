#!/bin/sh
# Бэкап БД: pg_dump + gzip, ротация 7 дней.
# Запускается из контейнера crm-backup (см. docker-compose.prod.yml).
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP="$(date +%F-%H%M)"
FILE="${BACKUP_DIR}/crm-${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date +%T)] dumping ${POSTGRES_DB} → ${FILE}"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h postgres \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    | gzip > "${FILE}"

# Ротация: удаляем бэкапы старше 7 дней
find "${BACKUP_DIR}" -name "crm-*.sql.gz" -type f -mtime +7 -delete

echo "[$(date +%T)] backup done. Current state:"
ls -la "${BACKUP_DIR}"
