"""Pydantic schemas for semantic search request and response."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from LAYER2.layer2.app.schemas.rfi import RFIRead


class SearchFilters(BaseModel):
    """All filters are optional and combinable."""

    msc_country: Optional[str] = Field(
        default=None, description="Filter by Member State, e.g. 'Germany'."
    )
    ctr_article_name: Optional[str] = Field(
        default=None,
        description="Filter by CTR article/section, e.g. 'Annex I, Section 63'.",
    )
    date_from: Optional[date] = Field(
        default=None, description="Filter RFIs received on or after this date."
    )
    date_to: Optional[date] = Field(
        default=None, description="Filter RFIs received on or before this date."
    )
    category: Optional[str] = Field(
        default=None, description="Filter by RFI category, e.g. 'Statistics'."
    )
    stage: Optional[str] = Field(
        default=None, description="Filter by current workflow stage."
    )


class SearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Free-text query — embedded and compared against stored RFI vectors.",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return.",
    )
    filters: Optional[SearchFilters] = None


class SearchResult(BaseModel):
    rfi: RFIRead
    score: float = Field(
        description="Cosine similarity score (0–1). Higher = more similar."
    )
    match_type: Literal["semantic", "filter"] = Field(
        description="'semantic' = vector search hit; 'filter' = exact filter match only."
    )


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


# ─── Hybrid search (pgvector → Neo4j enrich) ────────────────────────────────────


class HybridSearchRequest(BaseModel):
    """Request body for POST /search/hybrid."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Free-text query — embedded and searched against per-consideration vectors.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of consideration-level results to return.",
    )


class HybridSearchResult(BaseModel):
    """
    One consideration-level hit, combining pgvector similarity with
    Neo4j graph context.

    All ``Optional`` graph fields are ``null`` when Neo4j is unavailable
    (``neo4j_enriched`` will be ``false`` on the parent response).
    """

    # ── From pgvector ──────────────────────────────────────────────────────────────
    consideration_id: str = Field(
        description="Neo4j merge key, e.g. 'CT-2024-123456-12-00-SM01-001-C1'."
    )
    score: float = Field(
        description="Cosine similarity score (0–1). Higher = more similar."
    )
    concern_text: Optional[str] = Field(
        default=None, description="Reviewer's concern text stored in pgvector."
    )

    # ── From Neo4j (null when Neo4j unavailable) ─────────────────────────────
    rfi_id: Optional[str] = Field(default=None, description="Parent RFI identifier.")
    msc_country: Optional[str] = Field(
        default=None, description="Member State Concerned from graph."
    )
    indication_name: Optional[str] = Field(
        default=None, description="Therapeutic indication from graph."
    )
    ctr_article_name: Optional[str] = Field(
        default=None, description="CTR article / annex section from graph."
    )
    louvain_cluster: Optional[int] = Field(
        default=None,
        description="Louvain community ID from graph (if community detection has been run).",
    )
    centrality: Optional[float] = Field(
        default=None,
        description="Graph centrality score of the parent article node (if computed).",
    )


class HybridSearchResponse(BaseModel):
    """Response envelope for POST /search/hybrid."""

    results: list[HybridSearchResult]
    total: int
    query: str
    neo4j_enriched: bool = Field(
        description=(
            "True when Neo4j was reachable and enrichment data was returned. "
            "False when running in pgvector-only mode (graph fields are null)."
        )
    )
