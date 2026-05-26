import typing

from app.core.logging.logger import get_logger

logger = get_logger(__name__)
import asyncio
import uuid

import httpx
from sqlalchemy import text

from app.db.database import AsyncSessionLocal

API_URL = "http://localhost:8000"


async def verify() -> typing.Any:
    """
    Automatically generated docstring.
    """
    # Wait for the model cache to initialize
    logger.info("Waiting 5 seconds for services to fully initialize...")
    await asyncio.sleep(5)

    async with httpx.AsyncClient() as client:
        # 1. Health check
        logger.info("\n[*] Querying /health...")
        res = await client.get(f"{API_URL}/health")
        logger.info(f"Status: {res.status_code}")
        logger.info(f"Body: {res.text}\n")

        # 2. Metrics check
        logger.info("[*] Querying /metrics...")
        res = await client.get(f"{API_URL}/metrics")
        logger.info(f"Status: {res.status_code}")
        lines = res.text.split("\n")
        logger.info(f"First 10 lines of metrics:")
        for line in lines[:15]:
            logger.info(f"  {line}")
        logger.info()

        # 3. Admin stats check (requires user signup & login)
        logger.info("[*] Creating admin user for stats verification...")
        username = f"admin_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        password = "Password123"

        res = await client.post(
            f"{API_URL}/api/v1/auth/signup",
            json={"username": username, "email": email, "password": password},
        )
        if res.status_code not in [200, 201]:
            logger.info(f"Signup failed: {res.text}")
            return

        logger.info("[*] Escalating role to admin in DB...")
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE users SET role = 'admin' WHERE email = :email"),
                {"email": email},
            )
            await session.commit()

        logger.info("[*] Logging in admin...")
        res = await client.post(
            f"{API_URL}/api/v1/auth/login", json={"email": email, "password": password}
        )
        if res.status_code != 200:
            logger.info(f"Login failed: {res.text}")
            return

        token = res.json()["data"]["access_token"]

        logger.info("\n[*] Querying /api/v1/admin/stats...")
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get(f"{API_URL}/api/v1/admin/stats", headers=headers)
        logger.info(f"Status: {res.status_code}")
        logger.info(f"Body: {res.text}\n")


if __name__ == "__main__":
    asyncio.run(verify())
