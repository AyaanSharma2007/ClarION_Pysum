import asyncio
from neo4j import AsyncGraphDatabase

async def main():
    uri = "neo4j+s://9b50d02d.databases.neo4j.io"
    user = "9b50d02d"
    password = "iLnYkIW3LRqicOj4ysPGQ6LmuhhSuCW7Uc5anSWfAJs"
    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        await driver.verify_connectivity()
        print("Connected!")
        await driver.close()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
