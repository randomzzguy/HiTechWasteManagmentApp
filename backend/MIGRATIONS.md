# Database Migrations

This project uses Alembic for database schema migrations.

## Development
Tables are auto-created on startup via `create_all_tables()` in `database.py`.
This is fine for development but should not be used in production.

## Production

### Apply all pending migrations
```bash
alembic upgrade head
```

### Generate a new migration after model changes
```bash
alembic revision --autogenerate -m "describe your change"
```

### Rollback one migration
```bash
alembic downgrade -1
```

### View migration history
```bash
alembic history
```

## Notes
- Migration files are in `backend/alembic/versions/`
- The `env.py` reads `DATABASE_URL` from the environment via `pydantic-settings`
- Always review auto-generated migrations before applying them in production
- The initial migration (`initial_schema`) is a placeholder — re-run autogenerate against a live DB to get full DDL:
  ```bash
  alembic revision --autogenerate -m "initial_schema"
  ```
  Or simply rely on `create_all_tables()` for the first deployment and use Alembic for all subsequent schema changes.
