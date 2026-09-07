import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # get all rfis
        r = await client.get("http://localhost:8001/rfi/all")
        for rfi in r.json():
            for c in rfi.get("considerations", []):
                if "protocol version 5.0" in c.get("concern_text", ""):
                    cid = c["id"]
                    print("Found CID:", cid)
                    # test evaluate manual draft
                    res = await client.post(f"http://localhost:8000/api/draft/{cid}/evaluate", json={"draft_text": "blah blah"})
                    print("Evaluate response:", res.status_code, res.json())
                    break

asyncio.run(main())
