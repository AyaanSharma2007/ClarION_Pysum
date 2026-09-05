import sys
import os
import requests
import asyncio
from dotenv import load_dotenv

# Ensure we can import from the backend
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))
try:
    import load_rfi
    from neo4j import GraphDatabase
except ImportError:
    print("Warning: Could not import load_rfi or neo4j. Make sure you are in the correct virtual environment.")

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "LAYER2", "layer2", ".env"))

def generate_mock_data():
    records = []
    countries = ["Spain", "Germany", "France", "Italy", "Denmark"]
    indications = ["Type 2 Diabetes Mellitus", "Obesity", "Cardiovascular Disease", "Rare Disease"]
    concerns = [
        "The primary endpoint statistics are insufficiently powered for the subgroup analysis.",
        "Missing IMPD quality details for the biologic manufacturing process.",
        "Pharmacovigilance plan is incomplete regarding long-term follow-up.",
        "Informed consent form lacks specific GDPR clauses required by local law.",
        "Clinical protocol Section B does not clearly define the secondary endpoints."
    ]
    categories = [
        "statistics", "quality_impd", "safety_pharmacovigilance", "regulatory_admin", "clinical_protocol"
    ]
    
    # Generate 50 records to show volume
    for i in range(50):
        rfi_id = f"CT-2026-DEMO-{1000+i}"
        
        # Create a predictable but varied pattern for the demo
        country = countries[i % len(countries)]
        indication = indications[(i // len(countries)) % len(indications)]
        concern = concerns[i % len(concerns)]
        category = categories[i % len(categories)]
        
        record = {
            "rfi_id": rfi_id,
            "due_date": "2026-03-16",
            "response_date": "2026-03-06",
            "submit_date": "2026-03-05",
            "category": category,
            "owner_team": "EU-Hub-Regulatory",
            "msc": {"country": country},
            "indication": {"name": indication},
            "considerations": [
                {
                    "number": 1,
                    "concern_text": concern,
                    "ctr_article": {"name": "Part I - Regulatory"},
                    "response": {"text": "We have updated the dossier section as requested to address the concern."},
                    "outcome": {"status": "accepted" if i % 3 != 0 else "rejected"}
                }
            ]
        }
        records.append(record)
    return records

def seed_postgres(records):
    # Send to Layer 2 API (assumes it is running on port 8000)
    url = "http://localhost:8000/rfi/batch"
    payload = {"records": records}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"✅ Successfully seeded {len(records)} records to Postgres via Layer 2 API.")
    except requests.exceptions.ConnectionError:
        print("❌ Failed to connect to Layer 2 API. Make sure it is running (npm run dev:layer2).")
    except Exception as e:
        print(f"❌ Failed to seed Postgres: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")

def seed_neo4j(records):
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            for record in records:
                session.execute_write(load_rfi.load_record, record)
        print(f"✅ Successfully seeded {len(records)} records to Neo4j.")
    except Exception as e:
        print(f"❌ Failed to seed Neo4j: {e}")

if __name__ == "__main__":
    print("==================================================")
    print(" ClarION — Demo Data Seeding Script ")
    print("==================================================")
    print("Generating demo data...")
    records = generate_mock_data()
    
    print("Seeding Neo4j...")
    seed_neo4j(records)
    
    print("Seeding Postgres...")
    seed_postgres(records)
    print("Done!")
