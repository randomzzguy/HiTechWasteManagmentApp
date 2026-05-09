import asyncio
import sys
sys.path.insert(0, '.')

from database import get_db
from sqlalchemy import select, text

async def test_api():
    async for db in get_db():
        # Test scheduled waste batches
        result = await db.execute(text("SELECT COUNT(*) FROM scheduled_waste_batches"))
        sw_count = result.scalar()
        print(f"✅ Scheduled waste batches: {sw_count}")
        
        # Test recyclable records
        result = await db.execute(text("SELECT COUNT(*) FROM recyclable_records"))
        rec_count = result.scalar()
        print(f"✅ Recyclable records: {rec_count}")
        
        # Test destruction jobs
        result = await db.execute(text("SELECT COUNT(*) FROM destruction_jobs"))
        dest_count = result.scalar()
        print(f"❌ Destruction jobs: {dest_count}")
        
        # Test recycler deliveries
        result = await db.execute(text("SELECT COUNT(*) FROM recycler_deliveries"))
        del_count = result.scalar()
        print(f"❌ Recycler deliveries: {del_count}")

if __name__ == "__main__":
    asyncio.run(test_api())
