import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select, text
from database import get_db
from models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset_password():
    async for db in get_db():
        # Get admin user
        result = await db.execute(select(User).where(User.email == "admin@hitechwaste.com.my"))
        user = result.scalar_one_or_none()
        
        if user:
            # Update password
            user.hashed_password = pwd_context.hash("Admin@1234")
            await db.commit()
            print(f"✅ Password reset for {user.email}")
        else:
            print("❌ Admin user not found")

if __name__ == "__main__":
    asyncio.run(reset_password())
