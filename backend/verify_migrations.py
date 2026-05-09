#!/usr/bin/env python3
"""
Verify Alembic migrations are production-ready.
Checks for common issues and validates migration safety.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from alembic import command
from alembic.config import Config
from config import get_settings


def check_migration_safety():
    """Check if migrations are safe for production."""
    settings = get_settings()
    
    print("=" * 70)
    print("Alembic Migration Verification")
    print("=" * 70)
    print()
    
    # Check 1: Verify database connection
    print("1. Checking database connection...")
    try:
        import asyncpg
        import asyncio
        
        async def test_connection():
            conn = await asyncpg.connect(settings.sync_database_url)
            await conn.close()
            return True
        
        if asyncio.run(test_connection()):
            print("   ✅ Database connection successful")
        else:
            print("   ❌ Database connection failed")
            return False
    except Exception as e:
        print(f"   ❌ Database connection error: {e}")
        return False
    
    # Check 2: Verify migration files have downgrade functions
    print("\n2. Checking migration files have downgrade functions...")
    alembic_dir = Path(__file__).parent / "alembic" / "versions"
    migration_files = list(alembic_dir.glob("*.py"))
    
    all_have_downgrade = True
    for migration_file in migration_files:
        if migration_file.name.startswith("__"):
            continue
        
        content = migration_file.read_text()
        has_upgrade = "def upgrade()" in content
        has_downgrade = "def downgrade()" in content
        
        if has_upgrade and has_downgrade:
            print(f"   ✅ {migration_file.name} - has upgrade and downgrade")
        elif has_upgrade and not has_downgrade:
            print(f"   ⚠️  {migration_file.name} - missing downgrade function")
            all_have_downgrade = False
        else:
            print(f"   ❌ {migration_file.name} - missing upgrade function")
            all_have_downgrade = False
    
    if not all_have_downgrade:
        print("\n   ⚠️  Some migrations lack downgrade functions. This makes rollback impossible.")
        print("   Consider adding downgrade functions for safe production deployment.")
    
    # Check 3: Verify migration order
    print("\n3. Checking migration chain integrity...")
    try:
        alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
        command.current(alembic_cfg)
        print("   ✅ Migration chain is valid")
    except Exception as e:
        print(f"   ❌ Migration chain error: {e}")
        return False
    
    # Check 4: Get current migration status
    print("\n4. Checking current migration status...")
    try:
        alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
        current = command.current(alembic_cfg, verbose=True)
        print(f"   Current migration: {current}")
    except Exception as e:
        print(f"   ⚠️  Could not determine current migration: {e}")
    
    # Check 5: List all migrations
    print("\n5. Listing all migrations...")
    try:
        alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
        command.history(alembic_cfg)
    except Exception as e:
        print(f"   ❌ Could not list migrations: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("Migration Verification Complete")
    print("=" * 70)
    
    if all_have_downgrade:
        print("\n✅ All checks passed. Migrations are production-ready.")
        return True
    else:
        print("\n⚠️  Some issues found. Review warnings above before deploying.")
        return False


if __name__ == "__main__":
    success = check_migration_safety()
    sys.exit(0 if success else 1)
