import os
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

import httpx

from ..safety_gateway import screen_untrusted_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Intelligence Layer"])

# ── Configuration ──────────────────────────────────────────────────────────────
LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8001")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


async def pgvector_similarity_search(query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Semantic similarity search via Layer 2's pgvector-backed /search endpoint.
    Returns a list of matching considerations with their similarity scores.
    Falls back to empty results if Layer 2 is unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{LAYER2_URL}/search",
                json={
                    "query": query_text,
                    "top_k": top_k,
                    "owner_team": "EU-Hub-Regulatory",
                },
                headers={"X-Owner-Team": "EU-Hub-Regulatory"},
            )
            if resp.status_code == 200:
                data = resp.json()
                # Layer 2 returns results in a 'results' key or directly as a list
                results = data if isinstance(data, list) else data.get("results", [])
                return results
            else:
                logger.warning(
                    "Layer 2 search returned HTTP %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return []
    except httpx.ConnectError:
        logger.warning("Layer 2 not reachable at %s — returning empty search results.", LAYER2_URL)
        return []
    except Exception as e:
        logger.warning("pgvector similarity search failed: %s", e)
        return []


def neo4j_enrichment(consideration_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Enrich consideration IDs with structural/relational context from Neo4j.
    Returns MSC, Indication, CTR Article, and cluster info for each consideration.
    Falls back gracefully if Neo4j is unavailable or not configured.
    """
    if not NEO4J_URI or not NEO4J_PASSWORD or not consideration_ids:
        return []

    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.warning("neo4j package not installed — skipping graph enrichment.")
        return []

    ENRICH_QUERY = """
    MATCH (c:Consideration)<-[:HAS_CONSIDERATION]-(r:RFI)
    OPTIONAL MATCH (r)-[:SUBMITTED_TO]->(m:MSC)
    OPTIONAL MATCH (r)-[:INDICATION_TO]->(i:Indication)
    OPTIONAL MATCH (c)-[:REFERENCES]->(art:CTR_Articles)
    WHERE c.consideration_id IN $ids
    RETURN c.consideration_id AS consideration_id,
           c.concern_text AS concern_text,
           r.rfi_id AS rfi_id,
           m.msc_country AS msc_country,
           i.indication_name AS indication_name,
           art.ctr_article_name AS ctr_article_name
    """

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            result = session.run(ENRICH_QUERY, ids=consideration_ids)
            enriched = [dict(record) for record in result]
        driver.close()
        return enriched
    except Exception as e:
        logger.warning("Neo4j enrichment failed: %s", e)
        return []


@router.get("/search/hybrid")
async def hybrid_search(query: str = Query(...), top_k: int = 5):
    """
    Layer 3: Retrieve then Enrich (Clarion Bible §8.5).
    1. Screen query text for prompt injection (Safety Gateway §6.2).
    2. Search pgvector (Layer 2) for semantic similarity.
    3. Enrich with Neo4j graph structure (MSC, Indication, CTR Article).
    """
    screen = screen_untrusted_text(query)
    if screen["flagged"]:
        raise HTTPException(
            status_code=400,
            detail={"status": "quarantined", "reason": screen["matched_patterns"]}
        )

    # Step 1: Semantic search via Layer 2 pgvector
    search_results = await pgvector_similarity_search(query, top_k=top_k)

    # Extract consideration IDs for Neo4j enrichment
    consideration_ids = []
    for r in search_results:
        cid = r.get("consideration_id") or r.get("id")
        if cid:
            consideration_ids.append(cid)

    # Step 2: Enrich with Neo4j graph context
    enriched = neo4j_enrichment(consideration_ids)

    # Merge enrichment data back into search results
    enrichment_map = {e["consideration_id"]: e for e in enriched}
    merged_results = []
    for r in search_results:
        cid = r.get("consideration_id") or r.get("id")
        if cid and cid in enrichment_map:
            merged = {**r, **enrichment_map[cid]}
        else:
            merged = r
        merged_results.append(merged)

    return {"results": merged_results if merged_results else search_results}


@router.get("/recommendations")
async def recommend_responses(concern_text: str = Query(...), top_k: int = 5):
    """
    Layer 5: Outcome-Weighted Recommender (Clarion Bible §11).
    Over-fetches from hybrid search, then re-ranks by success_score.
    """
    screen = screen_untrusted_text(concern_text)
    if screen["flagged"]:
        raise HTTPException(
            status_code=400,
            detail={"status": "quarantined", "reason": screen["matched_patterns"]}
        )

    # Over-fetch for re-ranking
    search_results = await pgvector_similarity_search(concern_text, top_k=20)

    # Extract consideration IDs for Neo4j enrichment
    consideration_ids = []
    for r in search_results:
        cid = r.get("consideration_id") or r.get("id")
        if cid:
            consideration_ids.append(cid)

    enriched = neo4j_enrichment(consideration_ids)
    enrichment_map = {e["consideration_id"]: e for e in enriched}

    candidates = []
    for r in search_results:
        cid = r.get("consideration_id") or r.get("id")
        if cid and cid in enrichment_map:
            merged = {**r, **enrichment_map[cid]}
        else:
            merged = r
        candidates.append(merged)

    # Re-rank by weighted combination of similarity + success score
    ranked = sorted(
        candidates,
        key=lambda r: (r.get("similarity_score", 0) * 0.6 + r.get("success_score", 0.5) * 0.4),
        reverse=True,
    )

    return {"recommendations": ranked[:top_k]}
