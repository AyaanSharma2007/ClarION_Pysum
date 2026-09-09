import sys
import os
import asyncio
from dotenv import load_dotenv

# Load env vars first
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "layer2", ".env"))

# Import from Layer 2
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "layer2"))
try:
    from app.config import settings
    from app.models.rfi import Consideration
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
except ImportError:
    print("Warning: Could not import layer2 modules. Ensure you are in the correct virtual environment.")

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Warning: Could not import neo4j.")

async def check_postgres():
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Consideration.consideration_id_str))
        pg_ids = {row[0] for row in result.all() if row[0] is not None}
    await engine.dispose()
    return pg_ids

def check_neo4j():
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    with driver.session() as session:
        result = session.run("MATCH (c:Consideration) RETURN c.consideration_id AS id")
        neo4j_ids = {record["id"] for record in result}
    driver.close()
    return neo4j_ids

async def main():
    print("==================================================")
    print(" ClarION — Join-Key Contract Verification ")
    print("==================================================")
    
    print("Fetching IDs from Postgres (Layer 2)...")
    try:
        pg_ids = await check_postgres()
    except Exception as e:
        print(f"❌ Failed to connect to Postgres: {e}")
        return
        
    print("Fetching IDs from Neo4j (Layer 3)...")
    try:
        neo4j_ids = check_neo4j()
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        return
        
    print(f"Postgres consideration count: {len(pg_ids)}")
    print(f"Neo4j consideration count: {len(neo4j_ids)}")
    print("-" * 50)
    
    missing_in_neo4j = pg_ids - neo4j_ids
    missing_in_pg = neo4j_ids - pg_ids
    
    if not missing_in_neo4j and not missing_in_pg:
        print("✅ JOIN KEY CONTRACT VERIFIED: All consideration IDs match perfectly between Postgres and Neo4j.")
        print(f"Total synchronized IDs: {len(pg_ids)}")
    else:
        print("❌ JOIN KEY CONTRACT BROKEN!")
        if missing_in_neo4j:
            print(f"IDs in Postgres but missing in Neo4j ({len(missing_in_neo4j)}): {list(missing_in_neo4j)[:5]}")
        if missing_in_pg:
            print(f"IDs in Neo4j but missing in Postgres ({len(missing_in_pg)}): {list(missing_in_pg)[:5]}")

if __name__ == "__main__":
    asyncio.run(main())
