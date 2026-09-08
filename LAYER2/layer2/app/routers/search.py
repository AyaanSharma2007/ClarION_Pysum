"""
Search router — semantic + filtered search over stored RFIs.

Endpoints
---------
POST /search              — embed query, cosine similarity search, apply filters
GET  /rfi/{id}/similar    — find similar RFIs to a given record (recommender seam)

How semantic search works
-------------------------
1. The query string is embedded with the same model used at ingest.
2. pgvector computes cosine distance (<=> operator) between the query
   vector and all stored RFI embeddings.
3. Optional filters (country, article, dates, category, stage) are
   applied as WHERE clauses BEFORE the distance computation — this is
   more efficient than post-filtering.
4. Results are ordered by similarity score (highest first).

Integration notes for Layer 3 / Layer 5
-----------------------------------------
- Layer 3 (Neo4j recommender) should call POST /search with its own
  query text and combine Layer 2 semantic scores with graph-proximity
  scores before re-ranking.
- Layer 5 can call GET /rfi/{id}/similar to pre-fetch candidates and
  then re-rank by response success_score.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from LAYER2.layer2.app.database import get_db
from LAYER2.layer2.app.models.audit import WorkflowState
from LAYER2.layer2.app.models.rfi import (
    CTRArticle,
    Consideration,
    NCA,
    RFI,
    TherapeuticArea,
)
from LAYER2.layer2.app.routers.ingest import _load_options, _to_rfi_read
from LAYER2.layer2.app.schemas.search import (
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from LAYER2.layer2.app.services.embedding import embedding_service
from LAYER2.layer2.app.services.neo4j_service import neo4j_service
from LAYER2.layer2.app.services.recommender import recommend_responses
from LAYER2.layer2.app.utils.safety_gateway import screen_untrusted_text
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search"])

class RecommendationRequest(BaseModel):
    concern_text: str = Field(..., description="Draft concern text to find similar cases for")
    top_k: int = Field(5, description="Number of recommendations to return")
    min_similarity: float = Field(0.35, description="Minimum cosine similarity threshold")
    exclude_consideration_id: Optional[str] = Field(None, description="Consideration ID to exclude (e.g. self)")

class RecommendationResult(BaseModel):
    consideration_id: str
    concern_text: Optional[str]
    response_text: Optional[str]
    outcome_status: Optional[str]
    similarity_score: float
    success_score: float
    final_score: float
    rfi_id: Optional[str] = None
    msc_country: Optional[str] = None
    ctr_article_name: Optional[str] = None
    louvain_cluster: Optional[int] = None

class RecommendationResponse(BaseModel):
    results: list[RecommendationResult]
    query: str


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _apply_filters(query, filters):
    """
    Apply optional WHERE clauses to a SQLAlchemy select() statement.
    All filters combine with AND.
    """
    if filters is None:
        return query

    if filters.msc_country:
        query = query.join(NCA, RFI.nca_id == NCA.id).where(
            NCA.country == filters.msc_country
        )
    if filters.ctr_article_name:
        # Filter RFIs that have at least one consideration referencing this article
        query = query.join(
            Consideration, Consideration.rfi_id == RFI.id
        ).join(
            CTRArticle, Consideration.ctr_article_id == CTRArticle.id
        ).where(
            CTRArticle.name == filters.ctr_article_name
        ).distinct()
    if filters.date_from:
        query = query.where(RFI.received_at >= filters.date_from)
    if filters.date_to:
        query = query.where(RFI.received_at <= filters.date_to)
    if filters.category:
        query = query.where(RFI.category == filters.category)
    if filters.stage:
        query = query.join(
            WorkflowState, WorkflowState.rfi_id == RFI.id
        ).where(WorkflowState.current_stage == filters.stage)

    return query


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic + filtered search over all RFIs",
    description=(
        "Embeds the query string and runs cosine similarity search against "
        "stored RFI vectors. Optional filters narrow the candidate set first. "
        "Returns up to top_k results ordered by similarity score."
    ),
)
async def search_rfis(
    body: SearchRequest, db: AsyncSession = Depends(get_db)
):
    # ── 0. Safety Gateway (Bible §6.2) ────────────────────────────────────────
    screen = screen_untrusted_text(body.query)
    if screen["flagged"]:
        return SearchResponse(
            results=[], total=0, query=body.query,
        )

    # ── 1. Embed the query ───────────────────────────────────────────────────
    try:
        query_vec = await embedding_service.encode_async(body.query)
    except Exception as exc:
        logger.error("Embedding failed for search query: %s", exc)
        raise HTTPException(status_code=503, detail="Embedding service unavailable.")

    # ── 2. Build pgvector cosine similarity query ───────────────────────────
    # pgvector's <=> operator returns cosine distance (0=identical, 2=opposite).
    # We convert to similarity: score = 1 - distance.
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import cast, func, literal

    # query_vec is a Python list[float] from embedding_service
    vec_literal = cast(query_vec, Vector(len(query_vec)))

    distance_expr = RFI.embedding.op("<=>")(vec_literal)

    stmt = (
        select(RFI, (literal(1) - distance_expr).label("score"))
        .where(RFI.embedding.is_not(None))
        .options(*_load_options())
    )

    # ── 3. Apply filters ─────────────────────────────────────────────────────
    stmt = _apply_filters(stmt, body.filters)

    # ── 4. Order + limit ─────────────────────────────────────────────────────
    stmt = stmt.order_by(distance_expr).limit(body.top_k)

    rows = await db.execute(stmt)
    results = []
    for rfi, score in rows.all():
        results.append(
            SearchResult(
                rfi=_to_rfi_read(rfi),
                score=round(float(score), 4),
                match_type="semantic",
            )
        )

    return SearchResponse(results=results, total=len(results), query=body.query)


@router.get(
    "/rfi/{rfi_identifier}/similar",
    response_model=SearchResponse,
    summary="Find RFIs semantically similar to a given record",
    description=(
        "Convenience wrapper: fetches the target RFI's embedding and runs "
        "the same vector search as POST /search. Excludes the source record "
        "from results. Intended for Layer 5 (recommender) pre-fetch."
    ),
)
async def get_similar(
    rfi_identifier: str,
    top_k: int = 10,
    db: AsyncSession = Depends(get_db),
):
    try:
        u = uuid.UUID(rfi_identifier)
        stmt_src = select(RFI.id, RFI.embedding, RFI.rfi_text).where((RFI.id == u) | (RFI.rfi_id == rfi_identifier))
    except (ValueError, TypeError, AttributeError):
        stmt_src = select(RFI.id, RFI.embedding, RFI.rfi_text).where(RFI.rfi_id == rfi_identifier)

    result = await db.execute(stmt_src)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="RFI not found.")

    target_id, embedding, rfi_text = row
    if embedding is None:
        raise HTTPException(
            status_code=422,
            detail="This RFI has no embedding stored — cannot find similar records.",
        )

    from pgvector.sqlalchemy import Vector
    from sqlalchemy import cast, literal

    # embedding comes back from asyncpg as a Vector object — convert to list first
    embedding_list = list(embedding)
    vec_literal = cast(embedding_list, Vector(len(embedding_list)))
    distance_expr = RFI.embedding.op("<=>")(vec_literal)

    stmt = (
        select(RFI, (literal(1) - distance_expr).label("score"))
        .where(RFI.embedding.is_not(None))
        .where(RFI.id != target_id)  # exclude self
        .options(*_load_options())
        .order_by(distance_expr)
        .limit(top_k)
    )

    rows = await db.execute(stmt)
    results = [
        SearchResult(
            rfi=_to_rfi_read(rfi),
            score=round(float(score), 4),
            match_type="semantic",
        )
        for rfi, score in rows.all()
    ]

    return SearchResponse(
        results=results,
        total=len(results),
        query=rfi_text or "",
    )



# ─── Hybrid search ───────────────────────────────────────────────────────────────


@router.post(
    "/search/hybrid",
    response_model=HybridSearchResponse,
    summary="Hybrid semantic search: pgvector recall → Neo4j graph enrichment",
    description=(
        "Two-step retrieve-then-enrich pattern:\n\n"
        "1. **pgvector** embeds the query and runs cosine ANN against "
        "``consideration.embedding`` — returns the top-k consideration-level hits "
        "with their Neo4j merge keys (``consideration_id_str``).\n"
        "2. **Neo4j** (Layer 3) takes those IDs and returns structural context: "
        "MSC country, Indication, CTR article, Louvain cluster, centrality.\n\n"
        "When Neo4j is unavailable (``NEO4J_PASSWORD`` not set), the endpoint "
        "degrades gracefully to pgvector-only mode — ``neo4j_enriched`` is "
        "``false`` and all graph fields are ``null``."
    ),
)
async def hybrid_search(
    body: HybridSearchRequest, db: AsyncSession = Depends(get_db)
):
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import cast, literal

    # ── Step 0: Safety Gateway (Bible §6.2) ─────────────────────────────────────
    screen = screen_untrusted_text(body.query)
    if screen["flagged"]:
        return HybridSearchResponse(
            results=[], total=0, query=body.query,
            neo4j_enriched=False,
        )

    # ── Step 1: embed the query ─────────────────────────────────────────────────
    try:
        query_vec = await embedding_service.encode_async(body.query)
    except Exception as exc:
        logger.error("Embedding failed for hybrid search query: %s", exc)
        raise HTTPException(
            status_code=503, detail="Embedding service unavailable."
        )

    # ── Step 2: pgvector ANN on consideration.embedding ───────────────────────
    # Returns (consideration_id_str, concern_text, score) per hit.
    # Only rows that have both the bridge key AND an embedding are eligible.
    vec_literal = cast(query_vec, Vector(len(query_vec)))
    distance_expr = Consideration.embedding.op("<=>")(vec_literal)

    stmt = (
        select(
            Consideration.consideration_id_str,
            Consideration.concern_text,
            (literal(1) - distance_expr).label("score"),
        )
        .where(Consideration.embedding.is_not(None))
        .where(Consideration.consideration_id_str.is_not(None))
        .order_by(distance_expr)
        .limit(body.top_k)
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        return HybridSearchResponse(
            results=[], total=0, query=body.query, neo4j_enriched=False
        )

    # ── Step 3: enrich with Neo4j graph context ────────────────────────────
    ids = [r.consideration_id_str for r in rows]
    neo4j_map: dict[str, dict] = {}
    neo4j_enriched = False
    try:
        raw = await neo4j_service.enrich_considerations(ids)
        neo4j_map = {r["consideration_id"]: r for r in raw}
        neo4j_enriched = bool(raw)
    except Exception as exc:
        # Graceful degradation — log and continue without graph data.
        logger.warning("Neo4j enrichment failed, returning pgvector-only results: %s", exc)

    # ── Step 4: merge and return ───────────────────────────────────────────────
    results = []
    for row in rows:
        graph = neo4j_map.get(row.consideration_id_str, {})
        results.append(
            HybridSearchResult(
                consideration_id=row.consideration_id_str,
                score=round(float(row.score), 4),
                concern_text=row.concern_text,
                rfi_id=graph.get("rfi_id"),
                msc_country=graph.get("msc_country"),
                indication_name=graph.get("indication_name"),
                ctr_article_name=graph.get("ctr_article_name"),
                louvain_cluster=graph.get("louvain_cluster"),
                centrality=graph.get("centrality"),
            )
        )

    return HybridSearchResponse(
        results=results,
        total=len(results),
        query=body.query,
        neo4j_enriched=neo4j_enriched,
    )


# ─── Layer 5 Recommender ─────────────────────────────────────────────────────────

@router.post(
    "/search/recommend",
    response_model=RecommendationResponse,
    summary="Layer 5 Recommender: Outcome-weighted re-ranking",
    description=(
        "Over-fetches semantically similar considerations, assigns a success "
        "score based on their historical regulatory outcome, and re-ranks "
        "them using a 60/40 weighted formula (Similarity / Success)."
    ),
)
async def get_recommendations(
    body: RecommendationRequest, db: AsyncSession = Depends(get_db)
):
    # Safety Gateway
    screen = screen_untrusted_text(body.concern_text)
    if screen["flagged"]:
        return RecommendationResponse(results=[], query=body.concern_text)

    try:
        results = await recommend_responses(
            db,
            body.concern_text,
            top_k=body.top_k,
            min_similarity=body.min_similarity,
            exclude_consideration_id=body.exclude_consideration_id,
        )
    except Exception as exc:
        logger.error("Recommender failed: %s", exc)
        raise HTTPException(status_code=500, detail="Recommendation service error")
    
    return RecommendationResponse(results=results, query=body.concern_text)
