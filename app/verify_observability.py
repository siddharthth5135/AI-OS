import asyncio
import uuid

import httpx
from sqlalchemy import text

from app.db.database import AsyncSessionLocal

API_URL = "http://localhost:8000"


async def verify():
    # Wait for the model cache to initialize
    print("Waiting 5 seconds for services to fully initialize...")
    await asyncio.sleep(5)

    async with httpx.AsyncClient() as client:
        # 1. Health check
        print("\n[*] Querying /health...")
        res = await client.get(f"{API_URL}/health")
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}\n")

        # 2. Metrics check
        print("[*] Querying /metrics...")
        res = await client.get(f"{API_URL}/metrics")
        print(f"Status: {res.status_code}")
        lines = res.text.split("\n")
        print(f"First 10 lines of metrics:")
        for line in lines[:15]:
            print(f"  {line}")
        print()

        # 3. Admin stats check (requires user signup & login)
        print("[*] Creating admin user for stats verification...")
        username = f"admin_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        password = "Password123"

        res = await client.post(
            f"{API_URL}/api/v1/auth/signup",
            json={"username": username, "email": email, "password": password},
        )
        if res.status_code not in [200, 201]:
            print(f"Signup failed: {res.text}")
            return

        print("[*] Escalating role to admin in DB...")
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET role = 'admin' WHERE email = :email"),
                {"email": email},
            )
            await session.commit()

        print("[*] Logging in admin...")
        res = await client.post(
            f"{API_URL}/api/v1/auth/login", json={"email": email, "password": password}
        )
        if res.status_code != 200:
            print(f"Login failed: {res.text}")
            return

        token = res.json()["data"]["access_token"]

        print("\n[*] Querying /api/v1/admin/stats...")
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get(f"{API_URL}/api/v1/admin/stats", headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}\n")


if __name__ == "__main__":
    asyncio.run(verify())
