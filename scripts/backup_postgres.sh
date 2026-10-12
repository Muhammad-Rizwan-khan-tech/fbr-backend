#!/usr/bin/env bash
# ==============================================================================
# FBR Invoice Cloud - PostgreSQL & Documents Automated Backup Script
# Usage: ./scripts/backup_postgres.sh [backup_destination_dir]
# ==============================================================================
set -euo pipefail

DEST_DIR="${1:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${DEST_DIR}/fbr_invoice_cloud_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

mkdir -p "${DEST_DIR}"

echo "[INFO] Starting database backup at $(date)..."

# Support DATABASE_URL or individual PG* variables
if [[ -n "${DATABASE_URL:-}" ]] && [[ "${DATABASE_URL}" == postgres* ]]; then
  pg_dump --format=plain --no-owner --no-privileges "${DATABASE_URL}" | gzip -9 > "${BACKUP_FILE}"
else
  PGHOST="${PGHOST:-localhost}"
  PGPORT="${PGPORT:-5432}"
  PGUSER="${PGUSER:-postgres}"
  PGDATABASE="${PGDATABASE:-fbr_invoice_cloud}"
  
  pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" --no-owner --no-privileges | gzip -9 > "${BACKUP_FILE}"
fi

# Generate SHA256 checksum
sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "[SUCCESS] Backup completed: ${BACKUP_FILE} (${FILESIZE})"
echo "[SUCCESS] Checksum recorded: ${CHECKSUM_FILE}"

# Retention: Remove backups older than 30 days
echo "[INFO] Cleaning up backups older than 30 days..."
find "${DEST_DIR}" -name "fbr_invoice_cloud_*.sql.gz*" -mtime +30 -exec rm -f {} \; || true
echo "[INFO] Backup operation finished successfully."
