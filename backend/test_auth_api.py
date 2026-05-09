import asyncio
import httpx
import sys
sys.path.insert(0, '.')

async def test_api():
    # Login
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/auth/login",
            json={"username": "admin@hitechwaste.com.my", "password": "Admin@1234"}
        )
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            print(response.text)
            return
        
        token = response.json()["access_token"]
        print(f"✅ Login successful")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test scheduled waste batches
        response = await client.get(
            "http://localhost:8000/api/v1/compliance/sw-batches",
            headers=headers
        )
        print(f"✅ SW Batches API: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Items: {len(data.get('items', []))}")
            print(f"   Total: {data.get('total', 0)}")
        else:
            print(f"   Error: {response.text[:200]}")
        
        # Test recyclables stats
        response = await client.get(
            "http://localhost:8000/api/v1/recyclables/stats",
            headers=headers
        )
        print(f"✅ Recyclables Stats API: {response.status_code}")
        if response.status_code == 200:
            print(f"   Data: {response.json()}")
        else:
            print(f"   Error: {response.text[:200]}")
        
        # Test recyclables materials (what frontend actually calls)
        response = await client.get(
            "http://localhost:8000/api/v1/recyclables/records",
            headers=headers
        )
        print(f"✅ Recyclables Records API: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Items: {len(data.get('items', []))}")
            print(f"   Total: {data.get('total', 0)}")
        else:
            print(f"   Error: {response.text[:200]}")
        
        # Test destruction jobs
        response = await client.get(
            "http://localhost:8000/api/v1/destruction/jobs",
            headers=headers
        )
        print(f"✅ Destruction Jobs API: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Items: {len(data.get('items', []))}")
            print(f"   Total: {data.get('total', 0)}")
        else:
            print(f"   Error: {response.text[:200]}")

if __name__ == "__main__":
    asyncio.run(test_api())
