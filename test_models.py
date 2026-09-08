import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv("apps/backend/.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def test_api():
    async with httpx.AsyncClient() as client:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = await client.get(url)
        models = res.json()
        print([m['name'] for m in models.get('models', [])])

asyncio.run(test_api())
