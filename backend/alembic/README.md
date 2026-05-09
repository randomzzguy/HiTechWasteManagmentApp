# Alembic Database Migrations

This directory contains database migration scripts for Hi-Tech Waste Management.

## Migration Status

All migrations are production-ready with proper upgrade and downgrade functions.

## Running Migrations

### Development

```bash
# From backend directory
cd backend

# Generate a new migration
alembic revision --autogenerate -m "description_of_changes"

# Apply pending migrations
alembic upgrade head

# Rollback to previous migration
alembic downgrade -1

# View current migration version
alembic current

# View migration history
alembic history

# View SQL for a migration without applying it
alembic upgrade head --sql
```

### Production

```bash
# ALWAYS verify migrations before deploying to production
python verify_migrations.py

# Apply migrations (run from backend directory)
alembic upgrade head

# If migration fails, review error logs
# Fix the issue, then retry or rollback
```

## Migration Best Practices

### Before Deploying

1. **Verify migrations**: Run `python verify_migrations.py`
2. **Test migrations**: Apply migrations to a staging database first
3. **Backup database**: Always backup before production migrations
4. **Review SQL**: Check generated SQL for unexpected changes
5. **Plan rollback**: Know how to rollback if migration fails

### During Migration

1. **Monitor logs**: Watch for errors during migration
2. **Check duration**: Long-running migrations may need optimization
3. **Verify data**: Spot-check data integrity after migration
4. **Test application**: Run smoke tests after migration

### After Migration

1. **Verify application**: Ensure all features work correctly
2. **Monitor errors**: Check logs for migration-related errors
3. **Keep backup**: Retain backup for at least 7 days
4. **Document changes**: Record migration in changelog

## Migration Safety Checklist

- [ ] Migration has both upgrade() and downgrade() functions
- [ ] Downgrade tested on staging environment
- [ ] Database backup created before migration
- [ ] Migration reviewed by another developer
- [ ] Rollback procedure documented
- [ ] Application tested after migration
- [ ] Performance impact assessed
- [ ] Data integrity verified

## Troubleshooting

### Migration Fails

1. Check error logs for specific failure reason
2. Verify database connection is stable
3. Check for conflicting schema changes
4. Ensure all dependencies are installed
5. Review migration SQL for syntax errors

### Rollback Required

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Verify rollback successful
alembic current
```

### Migration Takes Too Long

1. Break large migration into smaller steps
2. Add indexes separately (after data migration)
3. Use batch processing for large data updates
4. Consider using direct SQL for bulk operations

## Common Issues

### "Target database is not up to date"

```bash
# This means the database is behind the migration files
# Apply missing migrations
alembic upgrade head
```

### "Revision identifier mismatch"

```bash
# The database has a migration not in the code
# Check current state
alembic current
alembic history

# Manually stamp the correct revision if needed
alembic stamp head
```

### Foreign Key Constraint Errors

1. Ensure referenced tables exist before adding FKs
2. Add FKs in separate migration after table creation
3. Use `deferrable initially deferred` if needed
4. Consider adding FKs after data migration

## Production Deployment Procedure

1. **Pre-deployment**
   - Run `python verify_migrations.py`
   - Test migrations on staging database
   - Create database backup
   - Notify team of upcoming deployment

2. **Deployment**
   - Put application in maintenance mode
   - Apply migrations: `alembic upgrade head`
   - Verify migration success
   - Run data integrity checks
   - Take application out of maintenance mode

3. **Post-deployment**
   - Monitor application logs
   - Verify all features working
   - Check performance metrics
   - Keep backup for rollback window

## Migration Naming Convention

Use descriptive, snake_case names:
- ✅ `add_user_last_login_column`
- ✅ `create_invoice_tables`
- ✅ `fix_client_address_nullable`
- ❌ `migration1`
- ❌ `changes`
- ❌ `update`

## Data Migration Tips

For large data migrations:

```python
def upgrade() -> None:
    # Process in batches to avoid memory issues
    batch_size = 1000
    offset = 0
    
    while True:
        # Process batch
        conn = op.get_bind()
        result = conn.execute(
            sa.text("SELECT id FROM large_table LIMIT :limit OFFSET :offset"),
            {"limit": batch_size, "offset": offset}
        )
        
        rows = result.fetchall()
        if not rows:
            break
        
        # Process rows
        for row in rows:
            # Your migration logic here
            pass
        
        offset += batch_size
```

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Migration Best Practices](https://docs.sqlalchemy.org/)
- [Database Migration Patterns](https://www.youtube.com/watch?v=6mI8x6d3x0Y)
