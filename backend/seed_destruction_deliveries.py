import asyncio
import sys
sys.path.insert(0, '.')

import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from database import get_db
from models.destruction import DestructionJob
from models.recycler_delivery import RecyclerDelivery

async def seed_destruction_jobs():
    async for db in get_db():
        # Check if data already exists
        result = await db.execute(text("SELECT COUNT(*) FROM destruction_jobs"))
        count = result.scalar()
        if count > 0:
            print(f"⚠️ Destruction jobs already exist ({count}), skipping")
            return
        
        # Use raw SQL to insert data to avoid type issues
        methods = ["shredding", "incineration", "landfill_compaction"]
        goods = ["Confidential documents", "Defective electronics", "Expired pharmaceuticals", "Counterfeit goods"]
        
        for i in range(15):
            await db.execute(text("""
                INSERT INTO destruction_jobs 
                (id, job_id, goods_description, quantity_units, weight_kg, destruction_method, 
                 destruction_date, destruction_location, certificate_issued, reason_codes, created_at, updated_at)
                VALUES (:id, NULL, :goods_description, :quantity_units, :weight_kg, :destruction_method,
                        :destruction_date, :destruction_location, :certificate_issued, NULL, :created_at, :updated_at)
            """), {
                "id": uuid.uuid4(),
                "goods_description": goods[i % len(goods)],
                "quantity_units": 10 + i,
                "weight_kg": 100 + (i * 50),
                "destruction_method": methods[i % len(methods)],
                "destruction_date": datetime.now(timezone.utc).date() + timedelta(days=i),
                "destruction_location": "Hi-Tech Destruction Facility",
                "certificate_issued": i % 3 == 0,
                "created_at": datetime.now(timezone.utc) - timedelta(days=30-i),
                "updated_at": datetime.now(timezone.utc),
            })
        
        await db.commit()
        print(f"✅ Seeded 15 destruction jobs")

async def seed_recycler_deliveries():
    async for db in get_db():
        # Check if data already exists
        result = await db.execute(text("SELECT COUNT(*) FROM recycler_deliveries"))
        count = result.scalar()
        if count > 0:
            print(f"⚠️ Recycler deliveries already exist ({count}), skipping")
            return
        
        # Use raw SQL to insert data
        materials = ["paper", "pet", "ferrous", "hdpe", "aluminium"]
        buyers = ["EcoRecycle Sdn Bhd", "GreenCycle Malaysia", "MetalWorks Sdn Bhd", "PlasticRecover"]
        
        for i in range(20):
            await db.execute(text("""
                INSERT INTO recycler_deliveries
                (id, delivery_number, client_id, material, quantity_kg, unit_price_myr_per_ton,
                 buyer_name, delivery_date, status, notes, created_at, updated_at)
                VALUES (:id, :delivery_number, :client_id, :material, :quantity_kg, :unit_price_myr_per_ton,
                        :buyer_name, :delivery_date, :status, :notes, :created_at, :updated_at)
            """), {
                "id": uuid.uuid4(),
                "delivery_number": f"DEL-{20260001 + i}",
                "client_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
                "material": materials[i % len(materials)],
                "quantity_kg": 500 + (i * 100),
                "unit_price_myr_per_ton": 800 + (i * 50),
                "buyer_name": buyers[i % len(buyers)],
                "delivery_date": datetime.now(timezone.utc) - timedelta(days=i),
                "status": "completed",
                "notes": f"Sample delivery {i+1}",
                "created_at": datetime.now(timezone.utc) - timedelta(days=i+1),
                "updated_at": datetime.now(timezone.utc),
            })
        
        await db.commit()
        print(f"✅ Seeded 20 recycler deliveries")

async def main():
    await seed_destruction_jobs()
    await seed_recycler_deliveries()
    print("\n✅ All seeding completed")

if __name__ == "__main__":
    asyncio.run(main())
