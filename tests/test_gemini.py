import asyncio
import traceback
from app.services.llm.gemini_client import get_llm_client

async def test_llm():
    try:
        client = get_llm_client()
        await client.initialize()
        res = await client.generate(prompt="Hello, say 'Test successful'")
        print("Gemini response:", res.text)
    except Exception as e:
        print("Gemini call failed:", e)
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm())
