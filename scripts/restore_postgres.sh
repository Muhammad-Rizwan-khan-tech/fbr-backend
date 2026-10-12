#!/usr/bin/env bash
# ==============================================================================
# FBR Invoice Cloud - PostgreSQL Restore Script
# Usage: ./scripts/restore_postgres.sh <backup_file.sql.gz>
# ==============================================================================
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <backup_file.sql.gz>"
  exit 1
fi

BACKUP_FILE="$1"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "[ERROR] Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

# Verify Checksum if present
if [ -f "${CHECKSUM_FILE}" ]; then
  echo "[INFO] Verifying backup checksum..."
  sha256sum -c "${CHECKSUM_FILE}"
  echo "[SUCCESS] Checksum verified."
fi

echo "[CAUTION] This operation will restore database from: ${BACKUP_FILE}"
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
  echo "[INFO] Restore cancelled."
  exit 0
fi

echo "[INFO] Restoring database..."
if [[ -n "${DATABASE_URL:-}" ]] && [[ "${DATABASE_URL}" == postgres* ]]; then
  gunzip -c "${BACKUP_FILE}" | psql "${DATABASE_URL}"
else
  PGHOST="${PGHOST:-localhost}"
  PGPORT="${PGPORT:-5432}"
  PGUSER="${PGUSER:-postgres}"
  PGDATABASE="${PGDATABASE:-fbr_invoice_cloud}"
  
  gunzip -c "${BACKUP_FILE}" | psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}"
fi

echo "[SUCCESS] Database restoration complete."
