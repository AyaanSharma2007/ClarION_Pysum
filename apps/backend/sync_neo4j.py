"""
sync_neo4j.py — Pull all RFIs from Layer 2 (Supabase/Postgres via REST)
and MERGE them into Neo4j.

This is safe to run repeatedly — MERGE is idempotent.

Usage:
    python apps/backend/sync_neo4j.py

Reads credentials from apps/backend/.env or environment variables:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    LAYER2_URL (default: http://localhost:8001)
"""

import os
import sys
import requests
from neo4j import GraphDatabase

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

NEO4J_URI     = os.getenv("NEO4J_URI")
NEO4J_USER    = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
LAYER2_URL    = os.getenv("LAYER2_URL", "http://localhost:8001")

if not NEO4J_URI or not NEO4J_PASSWORD:
    print("ERROR: Missing NEO4J_URI or NEO4J_PASSWORD in .env")
    sys.exit(1)

# ── Cypher MERGE query ───────────────────────────────────────────────────────
MERGE_QUERY = """
MERGE (rfi:RFI {rfi_id: $rfi_id})
SET rfi.due_date       = CASE WHEN $due_date IS NULL THEN null ELSE datetime($due_date + 'T00:00:00Z') END,
    rfi.response_date  = CASE WHEN $response_date IS NULL THEN null ELSE datetime($response_date + 'T00:00:00Z') END,
    rfi.submit_date    = CASE WHEN $submit_date IS NULL THEN null ELSE datetime($submit_date + 'T00:00:00Z') END,
    rfi.category       = $category,
    rfi.received_at    = CASE WHEN $received_at IS NULL THEN null ELSE datetime($received_at) END

MERGE (msc:MSC {msc_country: $msc_country})
MERGE (rfi)-[:SUBMITTED_TO]->(msc)

MERGE (ind:Indication {indication_name: $indication_name})
MERGE (rfi)-[:INDICATION_TO]->(ind)

WITH rfi
UNWIND $considerations AS c
  MERGE (cons:Consideration {consideration_id: c.id})
  SET cons.consideration_number = c.number,
      cons.concern_text         = c.concern_text,
      cons.response_text        = c.response_text
  MERGE (rfi)-[:HAS_CONSIDERATION]->(cons)

  MERGE (art:CTR_Articles {ctr_article_name: c.ctr_article_name})
  MERGE (cons)-[:REFERENCES]->(art)

  FOREACH (_ IN CASE WHEN c.outcome_status IS NOT NULL THEN [1] ELSE [] END |
    MERGE (out:Outcome {outcome_status: c.outcome_status})
    MERGE (cons)-[:STATUS]->(out)
  )
"""


def rfi_to_neo4j_params(rfi):
    """Convert a Layer 2 REST response record into MERGE_QUERY parameters."""
    considerations = []
    for c in rfi.get("considerations", []):
        considerations.append({
            "id":               c.get("consideration_id_str") or f'{rfi["rfi_id"]}-C{c.get("number", 1)}',
            "number":           c.get("number", 1),
            "concern_text":     c.get("concern_text") or "",
            "ctr_article_name": c.get("ctr_article_name") or "Unknown",
            "response_text":    c.get("response_text") or "",
            "outcome_status":   c.get("outcome_status"),
        })

    return {
        "rfi_id":          rfi["rfi_id"],
        "due_date":        rfi.get("due_date"),
        "response_date":   rfi.get("response_date"),
        "submit_date":     rfi.get("submit_date"),
        "category":        rfi.get("category"),
        "received_at":     rfi.get("received_at"),
        "msc_country":     rfi.get("nca_country") or "Unknown",
        "indication_name": rfi.get("therapeutic_area_name") or "Unknown",
        "considerations":  considerations,
    }


def main():
    # 1. Fetch all RFIs from Layer 2
    print(f"Fetching RFIs from {LAYER2_URL}/rfi ...")
    try:
        resp = requests.get(f"{LAYER2_URL}/rfi", timeout=15)
        resp.raise_for_status()
        rfis = resp.json()
    except Exception as e:
        print(f"ERROR: Could not fetch from Layer 2: {e}")
        sys.exit(1)

    if not rfis:
        print("No RFIs found in Layer 2 database.")
        return

    print(f"Found {len(rfis)} RFI(s) to sync.\n")

    # 2. Connect to Neo4j
    print(f"Connecting to Neo4j at {NEO4J_URI} ...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        print("Neo4j connected.\n")
    except Exception as e:
        print(f"ERROR: Cannot connect to Neo4j: {e}")
        driver.close()
        sys.exit(1)

    # 3. MERGE each RFI
    ok = 0
    errors = 0
    with driver.session() as session:
        for rfi in rfis:
            try:
                params = rfi_to_neo4j_params(rfi)
                session.execute_write(lambda tx, p: tx.run(MERGE_QUERY, **p), params)
                print(f"  ✓  {rfi['rfi_id']}  ({rfi.get('nca_country', '?')} · {rfi.get('therapeutic_area_name', '?')[:50]})")
                ok += 1
            except Exception as e:
                print(f"  ✗  {rfi.get('rfi_id', '?')}  ERROR: {e}")
                errors += 1

    driver.close()

    print(f"\nDone — {ok} synced, {errors} failed.")


if __name__ == "__main__":
    main()
