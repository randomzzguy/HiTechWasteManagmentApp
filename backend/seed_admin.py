"""Seed admin user for E2E testing."""
import asyncio
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from routers.auth import hash_password

DATABASE_URL = 'postgresql+asyncpg://hitech:password@localhost:5432/hitech_waste'

async def seed_admin():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        # Check if user exists
        result = await conn.execute(text("SELECT COUNT(*) FROM users WHERE email = 'admin@hitechwaste.com.my'"))
        count = result.scalar()
        if count == 0:
            hashed_pw = hash_password('admin123')
            await conn.execute(text('''
                INSERT INTO users (id, email, full_name, role, hashed_password, is_active, created_at)
                VALUES (:id, :email, :full_name, :role, :hashed_password, true, NOW())
            '''), {
                'id': str(uuid.uuid4()),
                'email': 'admin@hitechwaste.com.my',
                'full_name': 'Test Admin',
                'role': 'superadmin',
                'hashed_password': hashed_pw
            })
            print('Admin user created successfully')
        else:
            print('Admin user already exists')
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_admin())
