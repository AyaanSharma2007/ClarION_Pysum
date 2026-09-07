import sys
sys.path.append('LAYER2/layer2')
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.consideration import Consideration

async def main():
    async with AsyncSessionLocal() as db:
        stmt = select(Consideration)
        result = await db.execute(stmt)
        cons = result.scalars().all()
        for c in cons:
            if "protocol version 5.0" in c.concern_text:
                print("ID:", c.id)

asyncio.run(main())
