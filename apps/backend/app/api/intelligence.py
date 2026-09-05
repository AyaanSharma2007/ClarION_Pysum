from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List

from ..safety_gateway import screen_untrusted_text

router = APIRouter(tags=["Intelligence Layer"])

def pgvector_similarity_search(query_text: str, top_k: int) -> List[str]:
    # Mocking semantic similarity search in Postgres
    # Returns a list of consideration_ids
    return ["mock_rfi_1-C1", "mock_rfi_2-C2"]

def neo4j_enrichment(consideration_ids: List[str]) -> List[dict]:
    # Mocking Neo4j Graph traversal
    return [
        {
            "consideration_id": "mock_rfi_1-C1",
            "concern_text": "Need more data on adverse events.",
            "rfi_id": "mock_rfi_1",
            "msc_country": "Germany",
            "indication_name": "Type 2 Diabetes",
            "ctr_article_name": "Annex I, Section 63",
            "similarity_score": 0.95,
            "success_score": 0.8
        },
        {
            "consideration_id": "mock_rfi_2-C2",
            "concern_text": "Clarify statistical methodology.",
            "rfi_id": "mock_rfi_2",
            "msc_country": "Spain",
            "indication_name": "Type 2 Diabetes",
            "ctr_article_name": "Annex I, Section 50",
            "similarity_score": 0.85,
            "success_score": 0.9
        }
    ]

@router.get("/search/hybrid")
async def hybrid_search(query: str = Query(...), top_k: int = 5):
    """
    Layer 3: Retrieve then Enrich.
    1. Screen query text for prompt injection.
    2. Search pgvector for semantic similarity.
    3. Enrich with Neo4j graph structure.
    """
    screen = screen_untrusted_text(query)
    if screen["flagged"]:
        raise HTTPException(
            status_code=400, 
            detail={"status": "quarantined", "reason": screen["matched_patterns"]}
        )
        
    matching_ids = pgvector_similarity_search(query, top_k=top_k)
    enriched_results = neo4j_enrichment(matching_ids)
    
    return {"results": enriched_results}

@router.get("/recommendations")
async def recommend_responses(concern_text: str = Query(...), top_k: int = 5):
    """
    Layer 5: Outcome-Weighted Recommender.
    Re-ranks hybrid search results by success_score.
    """
    # Over-fetch for re-ranking
    screen = screen_untrusted_text(concern_text)
    if screen["flagged"]:
        raise HTTPException(
            status_code=400, 
            detail={"status": "quarantined", "reason": screen["matched_patterns"]}
        )
        
    candidates_ids = pgvector_similarity_search(concern_text, top_k=20)
    candidates = neo4j_enrichment(candidates_ids)
    
    ranked = sorted(
        candidates,
        key=lambda r: (r.get("similarity_score", 0) * 0.6 + r.get("success_score", 0.5) * 0.4),
        reverse=True,
    )
    
    return {"recommendations": ranked[:top_k]}
