#!/usr/bin/env bash
# scripts/backup.sh – Backup PostgreSQL database
set -euo pipefail

ENV_FILE="${1:-.env.production}"
source "$ENV_FILE"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
BACKUP_FILE="$BACKUP_DIR/ethical_ai_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Backing up database ${DB_NAME:-ethical_ai} …"
docker exec ethical-ai-db pg_dump \
  -U "${DB_USER:-postgres}" \
  "${DB_NAME:-ethical_ai}" | gzip > "$BACKUP_FILE"

echo "✅  Backup saved to $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Keep only the last 10 backups
ls -tp "$BACKUP_DIR"/ethical_ai_*.sql.gz | tail -n +11 | xargs -r rm --
echo "Old backups pruned (keeping last 10)."
