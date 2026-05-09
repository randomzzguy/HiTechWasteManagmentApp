# Database Backup and Restore

This directory contains scripts for automated PostgreSQL database backup and restore.

## Automated Backups

### Enable Backup Service

```bash
# Start backup service with daily backups
docker compose --profile backup up -d postgres-backup

# Check backup logs
docker logs hitech_postgres_backup
```

### Backup Configuration

Backups are configured with these environment variables:
- `RETENTION_DAYS`: How many days to keep backups (default: 30)
- `BACKUP_DIR`: Directory where backups are stored (default: /backups)
- `POSTGRES_PASSWORD`: Database password (from .env)

### Backup Schedule

- Backups run daily at midnight
- Retention policy keeps backups for 30 days by default
- Backups are compressed (.sql.gz)
- Logs are stored alongside backups

## Manual Backup

```bash
# Run manual backup
docker run --rm \
  -v $(pwd)/scripts/backup_postgres.sh:/backup_postgres.sh:ro \
  -v postgres_backups:/backups \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PASSWORD=your_password \
  postgres:15-alpine \
  sh -c "apk add --no-cache postgresql-client && /backup_postgres.sh"
```

## Restore from Backup

### Using Docker

```bash
# List available backups
docker run --rm \
  -v postgres_backups:/backups \
  postgres:15-alpine \
  ls -lh /backups/

# Restore from specific backup
docker run --rm -it \
  -v $(pwd)/scripts/restore_postgres.sh:/restore_postgres.sh:ro \
  -v postgres_backups:/backups \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PASSWORD=your_password \
  postgres:15-alpine \
  sh -c "apk add --no-cache postgresql-client && /restore_postgres.sh /backups/hitech_waste_YYYYMMDD_HHMMSS.sql.gz"
```

### Manual Restore

```bash
# Extract and restore
gunzip -c hitech_waste_YYYYMMDD_HHMMSS.sql.gz | psql -h postgres -U hitech -d hitech_waste
```

## Backup Locations

- Docker volume: `postgres_backups`
- Local mount: `./backups` (if mounted)
- Backup format: `hitech_waste_YYYYMMDD_HHMMSS.sql.gz`

## Testing Backups

### Test Backup Integrity

```bash
# Check if backup file is valid gzip
gzip -t hitech_waste_YYYYMMDD_HHMMSS.sql.gz

# Check if SQL is valid
gunzip -c hitech_waste_YYYYMMDD_HHMMSS.sql.gz | head -n 50
```

### Test Restore to Temporary Database

```bash
# Create temporary database
docker exec -it hitech_postgres psql -U hitech -c "CREATE DATABASE test_restore;"

# Restore to temporary database
gunzip -c hitech_waste_YYYYMMDD_HHMMSS.sql.gz | docker exec -i hitech_postgres psql -U hitech -d test_restore

# Verify restore
docker exec -it hitech_postgres psql -U hitech -d test_restore -c "SELECT COUNT(*) FROM users;"

# Clean up
docker exec -it hitech_postgres psql -U hitech -c "DROP DATABASE test_restore;"
```

## Off-Site Backup Storage

For production, consider:
- Sync backups to cloud storage (AWS S3, Wasabi, Backblaze B2)
- Use rclone for automated sync
- Encrypt backups before off-site storage

Example with rclone:
```bash
# Install rclone and configure remote
rclone config

# Sync backups to cloud
rclone sync /backups hitech-backup:postgres-backups
```

## Monitoring

### Check Backup Status

```bash
# View recent backups
docker run --rm \
  -v postgres_backups:/backups \
  postgres:15-alpine \
  ls -lh /backups/ | tail -n 10

# Check backup logs
docker run --rm \
  -v postgres_backups:/backups \
  postgres:15-alpine \
  cat /backups/backup_*.log | tail -n 50
```

### Alert on Backup Failure

Set up monitoring to alert when:
- Backup file not created within 24 hours
- Backup file is too small (potential failure)
- Backup logs contain errors

## Disaster Recovery

### Recovery Time Objective (RTO)
- Target: 1-2 hours
- Steps: Stop services → Restore database → Verify → Start services

### Recovery Point Objective (RPO)
- Target: 24 hours (daily backups)
- Can be reduced with hourly backups if needed

### Full Recovery Procedure

1. Stop all application services
2. Restore database from latest backup
3. Run database migrations if needed
4. Verify data integrity
5. Start application services
6. Monitor for errors
