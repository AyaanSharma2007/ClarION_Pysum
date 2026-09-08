"""
backfill_analytics_embeddings.py — Backfill embeddings and build Neo4j similarity graph.

1. Fetches all RFIs from Supabase `rfi_intake`.
2. Normalizes summaries, categories, and departments.
3. Generates 384-dim embeddings via `sentence-transformers/all-MiniLM-L6-v2`.
4. Saves embeddings and cleaned metadata back to Supabase `rfi_intake`.
5. Computes pairwise cosine similarity between all RFIs.
6. Populates Neo4j Knowledge Graph with:
   - RFI node properties (summary, department, category)
   - (:Department) and (:Category) nodes
   - [:SUBMITTED_BY] and [:HAS_CATEGORY] edges
   - [:IS_SIMILAR_TO {similarity: float}] edges for similarity >= 0.60
"""

import os
import sys
import logging
import numpy as np
from dotenv import load_dotenv

# Load backend env
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(os.path.abspath(env_path))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill")

CATEGORY_DEPT_MAP = {
    "statistics": "Biostatistics",
    "quality_impd": "Quality Assurance (CMC)",
    "safety_pharmacovigilance": "Pharmacovigilance",
    "regulatory_admin": "Regulatory Affairs",
    "clinical_protocol": "Clinical Operations",
    "gmp compliance": "Quality Assurance (CMC)",
    "informed consent": "Regulatory Affairs",
    "protocol design": "Clinical Operations",
    "safety reporting": "Pharmacovigilance",
    "labeling": "Regulatory Affairs",
    "bioequivalence": "Quality Assurance (CMC)",
    "documentation": "Regulatory Affairs",
}


def infer_department(row: dict) -> str:
    dept = row.get("department")
    if dept and isinstance(dept, str) and dept.strip() and dept.strip() != "Unknown":
        return dept.strip()
    cat = str(row.get("category") or "").lower()
    for key, mapped in CATEGORY_DEPT_MAP.items():
        if key in cat:
            return mapped
    return "Regulatory Affairs"


def infer_summary(row: dict) -> str:
    summary = (row.get("summary") or "").strip()
    if summary and summary != "RFI requires manual classification.":
        return summary
    cons = row.get("considerations") or []
    if isinstance(cons, list) and len(cons) > 0 and isinstance(cons[0], dict):
        text = cons[0].get("concern_text") or cons[0].get("text") or ""
        if text.strip():
            return text.strip()[:300]
    cat = row.get("category") or "regulatory compliance"
    dept = infer_department(row)
    return f"Request for clarification regarding {cat} under {dept} purview."


def main():
    logger.info("Initializing Backfill Pipeline...")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not supabase_url or not supabase_key:
        logger.error("Missing SUPABASE_URL or SUPABASE_KEY in environment.")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(supabase_url, supabase_key)

    # 1. Fetch rows from Supabase
    logger.info("Querying rfi_intake rows from Supabase...")
    res = sb.table("rfi_intake").select("*").execute()
    rows = res.data or []
    logger.info("Fetched %d records from rfi_intake.", len(rows))

    if not rows:
        logger.warning("No records found in rfi_intake. Exiting.")
        return

    # 2. Load SentenceTransformer
    logger.info("Loading sentence-transformers/all-MiniLM-L6-v2...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    summaries = []
    enriched_records = []

    for r in rows:
        rfi_id = r["rfi_id"]
        dept = infer_department(r)
        cat = r.get("category") or "General"
        urg = r.get("urgency") or "Medium"
        summary = infer_summary(r)

        summaries.append(summary)
        enriched_records.append({
            "id": r.get("id"),
            "rfi_id": rfi_id,
            "department": dept,
            "category": cat,
            "urgency": urg,
            "summary": summary,
        })

    # 3. Generate dense vector embeddings
    logger.info("Generating embeddings for %d summaries...", len(summaries))
    embeddings = model.encode(summaries, normalize_embeddings=True)
    logger.info("Embeddings generated. Shape: %s", embeddings.shape)

    # 4. Update Supabase with embeddings & metadata
    logger.info("Updating Supabase rfi_intake with embeddings and clean metadata...")
    for i, rec in enumerate(enriched_records):
        emb_list = embeddings[i].tolist()
        rec["embedding"] = emb_list
        update_payload = {
            "department": rec["department"],
            "category": rec["category"],
            "urgency": rec["urgency"],
            "summary": rec["summary"],
            "embedding": emb_list,
        }
        try:
            sb.table("rfi_intake").update(update_payload).eq("id", rec["id"]).execute()
        except Exception as e:
            logger.warning("Failed to update row id=%s rfi_id=%s: %s", rec["id"], rec["rfi_id"], e)

    logger.info("Supabase backfill complete!")

    # 5. Compute pairwise cosine similarities
    # embeddings is normalized, so dot product == cosine similarity
    logger.info("Computing pairwise cosine similarity matrix...")
    sim_matrix = np.dot(embeddings, embeddings.T)
    n = len(enriched_records)

    similar_pairs = []
    # Using similarity threshold >= 0.60 for related regulatory questions
    SIMILARITY_THRESHOLD = 0.60

    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= SIMILARITY_THRESHOLD:
                similar_pairs.append((
                    enriched_records[i]["rfi_id"],
                    enriched_records[j]["rfi_id"],
                    round(score, 4),
                    enriched_records[i]["summary"],
                    enriched_records[j]["summary"],
                ))

    logger.info("Found %d similar RFI pairs with cosine similarity >= %.2f", len(similar_pairs), SIMILARITY_THRESHOLD)
    for p in similar_pairs[:10]:
        logger.info("  Pair: %s <-> %s (sim: %.4f)", p[0], p[1], p[2])

    # 6. Populate Neo4j Knowledge Graph
    if not neo4j_uri or not neo4j_password:
        logger.warning("NEO4J credentials not found. Skipping Neo4j sync.")
        return

    logger.info("Connecting to Neo4j AuraDB at %s...", neo4j_uri)
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        with driver.session() as session:
            # First, ensure RFI nodes and Department / Category nodes exist
            for rec in enriched_records:
                session.run(
                    """
                    MERGE (rfi:RFI {rfi_id: $rfi_id})
                    SET rfi.summary = $summary,
                        rfi.department = $department,
                        rfi.category = $category,
                        rfi.urgency = $urgency

                    MERGE (dept:Department {name: $department})
                    MERGE (rfi)-[:SUBMITTED_BY]->(dept)

                    MERGE (cat:Category {name: $category})
                    MERGE (rfi)-[:HAS_CATEGORY]->(cat)
                    """,
                    rfi_id=rec["rfi_id"],
                    summary=rec["summary"],
                    department=rec["department"],
                    category=rec["category"],
                    urgency=rec["urgency"],
                )

            logger.info("Merged %d RFI nodes with Department and Category relationships in Neo4j.", len(enriched_records))

            # Create IS_SIMILAR_TO edges
            edge_count = 0
            for src_id, tgt_id, score, _, _ in similar_pairs:
                if src_id != tgt_id:
                    session.run(
                        """
                        MATCH (a:RFI {rfi_id: $src_id})
                        MATCH (b:RFI {rfi_id: $tgt_id})
                        MERGE (a)-[r:IS_SIMILAR_TO]->(b)
                        SET r.similarity = $score
                        MERGE (b)-[r2:IS_SIMILAR_TO]->(a)
                        SET r2.similarity = $score
                        """,
                        src_id=src_id,
                        tgt_id=tgt_id,
                        score=score,
                    )
                    edge_count += 2

            logger.info("Created/Updated %d IS_SIMILAR_TO edges in Neo4j Knowledge Graph.", edge_count)

            # Mark duplicate flag in Supabase if RFI has high similarity (> 0.85)
            duplicate_rfis = set()
            for src_id, tgt_id, score, _, _ in similar_pairs:
                if score >= 0.85:
                    duplicate_rfis.add(src_id)
                    duplicate_rfis.add(tgt_id)

            if duplicate_rfis:
                logger.info("Marking %d RFIs with is_duplicate=True in Supabase...", len(duplicate_rfis))
                for dup_id in duplicate_rfis:
                    try:
                        sb.table("rfi_intake").update({"is_duplicate": True}).eq("rfi_id", dup_id).execute()
                    except Exception as e:
                        logger.warning("Failed to mark duplicate flag for %s: %s", dup_id, e)

    finally:
        driver.close()

    logger.info("✅ BACKFILL AND GRAPH POPULATION COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
