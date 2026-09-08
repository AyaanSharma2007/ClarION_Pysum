import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv("apps/backend/.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def test_api():
    base64_pdf = "dGVzdA=="
    prompt = "Extract RFI"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "application/pdf",
                            "data": base64_pdf
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    async with httpx.AsyncClient() as client:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key={GEMINI_API_KEY}"
        res = await client.post(url, json=payload)
        print(res.status_code)
        print(res.json())

asyncio.run(test_api())
