#!/bin/sh
# Точка входа контейнера crm-backup: бесконечный цикл со сном до 4:00 каждые сутки.
# В контейнере postgres:alpine нет cron, поэтому делаем sleep-loop вручную.
set -eu

while true; do
    NOW="$(date +%H:%M)"
    if [ "${NOW}" = "04:00" ]; then
        /scripts/backup_db.sh || echo "backup failed: $?"
        sleep 70  # чтобы не запустить два раза подряд внутри той же минуты
    fi
    sleep 30
done
