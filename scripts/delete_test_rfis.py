import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from layer2.app.config import settings
from neo4j import AsyncGraphDatabase

async def main():
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    # Don't specify database, use default for community edition
    async with driver.session() as session:
        query = """
        MATCH (r:RFI)
        WHERE r.rfi_id STARTS WITH 'TEST'
        DETACH DELETE r
        """
        result = await session.run(query)
        summary = await result.consume()
        print(f"Deleted {summary.counters.nodes_deleted} nodes.")
    await driver.close()

if __name__ == "__main__":
    asyncio.run(main())
