import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Try direct Supabase connection
DIRECT_URL_REAL = "postgresql+asyncpg://postgres:vj5%,!jSVW86S5m|@db.hjgoomssudhyeowyeukx.supabase.co:5432/postgres"

async def test():
    print("Testing connection to:", DIRECT_URL_REAL)
    try:
        engine = create_async_engine(DIRECT_URL_REAL)
        async with engine.connect() as conn:
            res = await conn.execute(text("select 1"))
            print("Successfully connected to direct Supabase! Result:", res.scalar())
        await engine.dispose()
    except Exception as e:
        print("Direct Supabase connection failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
