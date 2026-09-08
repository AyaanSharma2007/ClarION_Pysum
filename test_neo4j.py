import os
import sys
from dotenv import load_dotenv

load_dotenv("apps/backend/.env")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

print("URI:", NEO4J_URI)
print("USER:", NEO4J_USER)

from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Connected to Neo4j successfully!")
except Exception as e:
    print("Failed to connect to Neo4j:", e)
