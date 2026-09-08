import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv("apps/backend/.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def test_api():
    payload1 = {
        "contents": [{"parts": [{"text": "hello"}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    payload2 = {
        "contents": [{"parts": [{"text": "hello"}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    async with httpx.AsyncClient() as client:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key={GEMINI_API_KEY}"
        res1 = await client.post(url, json=payload1)
        print("response_mime_type:", res1.json())
        res2 = await client.post(url, json=payload2)
        print("responseMimeType:", res2.json())

asyncio.run(test_api())
