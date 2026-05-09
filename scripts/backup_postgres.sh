#!/bin/bash
# =============================================================
# Hi-Tech Waste Management - PostgreSQL Backup Script
# Automated database backup with retention policy
# =============================================================

set -e

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-hitech}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-password}"
POSTGRES_DB="${POSTGRES_DB:-hitech_waste}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create backup directory with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/hitech_waste_${TIMESTAMP}.sql.gz"
BACKUP_LOG="${BACKUP_DIR}/backup_${TIMESTAMP}.log"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$BACKUP_LOG"
}

# Start backup
log "Starting PostgreSQL backup for database: ${POSTGRES_DB}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Perform backup
log "Running pg_dump..."
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-owner \
    --no-acl \
    --format=plain \
    --compress=9 \
    --file="$BACKUP_FILE" \
    2>&1 | tee -a "$BACKUP_LOG"

# Check if backup was successful
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup completed successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    log "ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups (retention policy)
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "hitech_waste_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "backup_*.log" -type f -mtime +${RETENTION_DAYS} -delete

# List remaining backups
log "Remaining backups:"
ls -lh "$BACKUP_DIR"/hitech_waste_*.sql.gz 2>/dev/null | tee -a "$BACKUP_LOG" || log "No backups found"

log "Backup process completed"
