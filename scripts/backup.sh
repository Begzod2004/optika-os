#!/bin/bash
# Optika OS kunlik PostgreSQL backup (pg_dump + gzip + 14 kunlik rotatsiya).
# Serverda /opt/optika-os/backup.sh sifatida o'rnatilgan, cron: 0 3 * * *
set -euo pipefail
BACKUP_DIR=/opt/optika-os/backups
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d-%H%M%S)
OUT="$BACKUP_DIR/optika-$TS.sql.gz"
docker exec optika-postgres-1 pg_dump -U optika optika | gzip > "$OUT"
if [ ! -s "$OUT" ]; then echo "$(date) XATO: backup bo'sh"; rm -f "$OUT"; exit 1; fi
find "$BACKUP_DIR" -name "optika-*.sql.gz" -mtime +14 -delete
echo "$(date) OK: $OUT ($(du -h "$OUT" | cut -f1))"
