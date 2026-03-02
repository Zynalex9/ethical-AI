#!/usr/bin/env bash
# scripts/restore.sh – Restore PostgreSQL database from backup
set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: ./scripts/restore.sh <backup_file> [env_file]"
  echo "  e.g. ./scripts/restore.sh ./backups/ethical_ai_20260101_120000.sql.gz"
  exit 1
fi

BACKUP_FILE="$1"
ENV_FILE="${2:-.env.production}"
source "$ENV_FILE"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: $BACKUP_FILE not found."
  exit 1
fi

echo "⚠️  This will OVERWRITE the database '${DB_NAME:-ethical_ai}'."
read -rp "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "Restoring from $BACKUP_FILE …"
gunzip -c "$BACKUP_FILE" | docker exec -i ethical-ai-db \
  psql -U "${DB_USER:-postgres}" "${DB_NAME:-ethical_ai}"

echo "✅  Database restored."
