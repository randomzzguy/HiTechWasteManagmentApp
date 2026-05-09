#!/bin/bash
# =============================================================
# Hi-Tech Waste Management - PostgreSQL Restore Script
# Restore database from backup file
# =============================================================

set -e

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-hitech}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-password}"
POSTGRES_DB="${POSTGRES_DB:-hitech_waste}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/hitech_waste_*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Confirm restore
log "WARNING: This will replace all data in database: ${POSTGRES_DB}"
log "Backup file: ${BACKUP_FILE}"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    log "Restore cancelled"
    exit 0
fi

# Start restore
log "Starting PostgreSQL restore from: ${BACKUP_FILE}"

# Drop existing database (optional - comment out if you want to append instead)
log "Dropping existing database..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"

# Create database
log "Creating database..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -c "CREATE DATABASE ${POSTGRES_DB};"

# Restore from backup
log "Restoring database from backup..."
gunzip -c "$BACKUP_FILE" | PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB"

if [ $? -eq 0 ]; then
    log "Restore completed successfully!"
    log "Database: ${POSTGRES_DB}"
    log "Backup file: ${BACKUP_FILE}"
else
    log "ERROR: Restore failed!"
    exit 1
fi
