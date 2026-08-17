# Optika OS — backupdan tiklash

Kunlik backuplar serverda: `/opt/optika-os/backups/optika-YYYYMMDD-HHMMSS.sql.gz`
Cron har kuni 03:00 da ishlaydi, 14 kunlik nusxa saqlanadi.

## Tiklash (butun bazani qaytarish)
```bash
BK=/opt/optika-os/backups/optika-XXXX.sql.gz   # kerakli nusxani tanlang
# DIQQAT: bu joriy ma'lumotni almashtiradi
docker exec optika-postgres-1 psql -U optika -d postgres -c "DROP DATABASE optika;"
docker exec optika-postgres-1 psql -U optika -d postgres -c "CREATE DATABASE optika;"
gunzip -c "$BK" | docker exec -i optika-postgres-1 psql -U optika -d optika
docker compose -p optika -f /opt/optika-os/docker-compose.prod.yml restart backend
```

## Qo'lda backup olish
```bash
/opt/optika-os/backup.sh
```
