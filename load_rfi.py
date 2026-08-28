"""
RFI Nexus — incremental loader.

Reads RFI records in the JSON shape defined by rfi_extraction_schema.json
(the output format your teammate's PDF-parsing pipeline produces) and
writes them into Neo4j using MERGE, so this is safe to run repeatedly and
safe to run on just ONE new RFI at a time — no need to touch or re-upload
any existing data.

Usage:
    python load_rfi.py path/to/new_rfi.json         # load a single new RFI
    python load_rfi.py path/to/folder_of_json/       # load every .json file in a folder

Credentials are read from environment variables — never hardcode them,
especially given the confidentiality requirement on this data.
    NEO4J_URI       e.g. neo4j+s://xxxx.databases.neo4j.io
    NEO4J_USER      e.g. neo4j
    NEO4J_PASSWORD
"""

import os
import sys
import json
from neo4j import GraphDatabase

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

MERGE_QUERY = """
MERGE (rfi:RFI {rfi_id: $rfi_id})
SET rfi.due_date       = CASE WHEN $due_date IS NULL THEN null ELSE datetime($due_date) END,
    rfi.response_date  = CASE WHEN $response_date IS NULL THEN null ELSE datetime($response_date) END,
    rfi.submit_date    = CASE WHEN $submit_date IS NULL THEN null ELSE datetime($submit_date) END

MERGE (msc:MSC {msc_country: $msc_country})
MERGE (rfi)-[:SUBMITTED_TO]->(msc)

MERGE (ind:Indication {indication_name: $indication_name})
MERGE (rfi)-[:INDICATION_TO]->(ind)

WITH rfi
UNWIND $considerations AS c
  MERGE (cons:Consideration {consideration_id: c.id})
  SET cons.consideration_number = c.number,
      cons.concern_text = c.concern_text
  MERGE (rfi)-[:HAS_CONSIDERATION]->(cons)

  MERGE (art:CTR_Articles {ctr_article_name: c.ctr_article_name})
  MERGE (cons)-[:REFERENCES]->(art)

  MERGE (resp:Response {response_text: c.response_text})
  MERGE (cons)-[:HAS_RESPONSE]->(resp)

  FOREACH (_ IN CASE WHEN c.outcome_status IS NOT NULL THEN [1] ELSE [] END |
    MERGE (out:Outcome {outcome_status: c.outcome_status})
    MERGE (cons)-[:STATUS]->(out)
  )
"""


def _flatten_considerations(record):
    """Turns the nested `considerations` array from the extraction JSON
    into the flat parameter shape the Cypher UNWIND expects."""
    out = []
    for c in record["considerations"]:
        out.append({
            "id": f'{record["rfi_id"]}-C{c["number"]}',
            "number": c["number"],
            "concern_text": c["concern_text"],
            "ctr_article_name": c["ctr_article"]["name"],
            "response_text": c["response"]["text"],
            "outcome_status": (c.get("outcome") or {}).get("status"),
        })
    return out


def load_record(tx, record):
    tx.run(
        MERGE_QUERY,
        rfi_id=record["rfi_id"],
        due_date=record.get("due_date"),
        response_date=record.get("response_date"),
        submit_date=record.get("submit_date"),
        msc_country=record["msc"]["country"],
        indication_name=record["indication"]["name"],
        considerations=_flatten_considerations(record),
    )


def load_path(driver, path):
    files = []
    if os.path.isdir(path):
        files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".json")]
    elif os.path.isfile(path):
        files = [path]
    else:
        raise FileNotFoundError(f"No such file or directory: {path}")

    with driver.session() as session:
        for filepath in files:
            with open(filepath, "r", encoding="utf-8") as f:
                record = json.load(f)
            session.execute_write(load_record, record)
            print(f"Loaded {record['rfi_id']}  (from {os.path.basename(filepath)})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python load_rfi.py <path/to/rfi.json or folder/>")
        sys.exit(1)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        load_path(driver, sys.argv[1])
    finally:
        driver.close()