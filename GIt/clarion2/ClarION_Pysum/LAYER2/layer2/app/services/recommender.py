"""
Layer 5 — Recommender Engine (Bible §11).

Takes a drafted concern text, fetches similar past considerations via pgvector,
and re-ranks the responses based on regulatory outcome (success score).

Formula: Score = (Similarity * 0.6) + (Success_Score * 0.4)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, literal

from app.models.rfi import Consideration
from app.services.embedding import embedding_service
from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


async def get_success_score(outcome_status: str | None) -> float:
    """Map outcome status to a numerical success score (0.0 to 1.0)."""
    if outcome_status == "accepted":
        return 1.0
    elif outcome_status == "follow-up-required":
        return 0.5
    elif outcome_status == "rejected":
        return 0.0
    return 0.5  # default if unknown


async def recommend_responses(
    db: AsyncSession,
    concern_text: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    1. Embed query
    2. Over-fetch top 20 candidates via pgvector
    3. Calculate success score for each candidate
    4. Re-rank using 60/40 formula
    5. Return top_k
    """
    # Over-fetch for re-ranking
    fetch_k = max(20, top_k * 3)

    query_vec = await embedding_service.encode_async(concern_text)
    vec_literal = cast(query_vec, Vector(len(query_vec)))
    distance_expr = Consideration.embedding.op("<=>")(vec_literal)

    # 1. Fetch from pgvector
    stmt = (
        select(
            Consideration.consideration_id_str,
            Consideration.concern_text,
            Consideration.response_text,
            Consideration.outcome_status,
            (literal(1) - distance_expr).label("similarity_score"),
        )
        .where(Consideration.embedding.is_not(None))
        .where(Consideration.consideration_id_str.is_not(None))
        .order_by(distance_expr)
        .limit(fetch_k)
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        return []

    # 2. Re-rank
    candidates = []
    for row in rows:
        sim_score = float(row.similarity_score)
        success_score = await get_success_score(row.outcome_status)
        final_score = (sim_score * 0.6) + (success_score * 0.4)
        
        candidates.append({
            "consideration_id": row.consideration_id_str,
            "concern_text": row.concern_text,
            "response_text": row.response_text,
            "outcome_status": row.outcome_status,
            "similarity_score": round(sim_score, 4),
            "success_score": success_score,
            "final_score": round(final_score, 4),
        })

    # Sort descending by final_score
    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    top_candidates = candidates[:top_k]

    # 3. Enrich top candidates with Neo4j context
    ids = [c["consideration_id"] for c in top_candidates]
    neo4j_map = {}
    try:
        raw = await neo4j_service.enrich_considerations(ids)
        neo4j_map = {r["consideration_id"]: r for r in raw}
    except Exception as exc:
        logger.warning("Neo4j enrichment failed for recommender: %s", exc)

    for c in top_candidates:
        graph = neo4j_map.get(c["consideration_id"], {})
        c["rfi_id"] = graph.get("rfi_id")
        c["msc_country"] = graph.get("msc_country")
        c["ctr_article_name"] = graph.get("ctr_article_name")
        c["louvain_cluster"] = graph.get("louvain_cluster")

    return top_candidates
