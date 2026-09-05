"""
Pydantic schemas for RFI ingestion and read responses.

RFICreate mirrors rfi_extraction_schema.json exactly — the field names,
nesting structure, and required/optional semantics are identical so
Layer 1 can POST its validated output here without any transformation.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ─── Valid workflow stages (Bible §6.4 / §7 status enum) ──────────────────────

VALID_STAGES: list[str] = [
    "received",
    "ready_for_response",
    "awaiting_response",
    "drafting",
    "pending_approval",
    "approved",
    "submitted",
]

# ─── Sub-objects matching rfi_extraction_schema.json ──────────────────────────


class MSCSchema(BaseModel):
    """Maps to (RFI)-[:SUBMITTED_TO]->(MSC) in the graph."""
    country: str = Field(
        description="Member State Concerned — exact country name, not abbreviated."
    )


class IndicationSchema(BaseModel):
    """Maps to (RFI)-[:INDICATION_TO]->(Indication) in the graph."""
    name: str = Field(
        description="Therapeutic indication / disease, e.g. 'Type 2 Diabetes Mellitus'."
    )


class CTRArticleSchema(BaseModel):
    """Maps to (Consideration)-[:REFERENCES]->(CTRArticle) in the graph."""
    name: str = Field(
        description="Regulation section, e.g. 'Annex I, Section 63' or 'Article 6'."
    )


class ResponseSchema(BaseModel):
    """Maps to (Consideration)-[:HAS_RESPONSE]->(Response) in the graph."""
    text: str = Field(description="Sponsor's verbatim response text.")


class OutcomeSchema(BaseModel):
    """Maps to (Consideration)-[:STATUS]->(Outcome) in the graph."""
    status: Optional[str] = Field(
        default=None,
        description="accepted | follow-up-required | rejected. Null at extraction time.",
    )


# ─── Inbound (write) schemas ───────────────────────────────────────────────────


class ConsiderationCreate(BaseModel):
    number: int = Field(ge=1, description="Consideration number from the document.")
    concern_text: Optional[str] = Field(
        default=None,
        description="Verbatim reviewer concern/question from the 'Consideration:' field. "
        "Optional — Layer 1 payloads may not include it (depends on extraction schema version).",
    )
    ctr_article: CTRArticleSchema
    response: ResponseSchema
    outcome: Optional[OutcomeSchema] = None


class RFICreate(BaseModel):
    """
    The exact shape that Layer 1 POSTs to /rfi.
    All fields mirror rfi_extraction_schema.json — do NOT rename them
    without updating the graph model in Layer 3 too.
    """

    rfi_id: str = Field(
        description="Unique identifier as printed, e.g. 'CT-2024-123456-12-00-SM01-001'."
    )
    # Bible §7 — RFI type and source document reference
    rfi_type: Optional[str] = Field(
        default=None,
        description="'validation' or 'assessment'. Optional until Layer 1 adds it.",
    )
    source_document_ref: Optional[str] = Field(
        default=None,
        description="Reference to original PDF/source document — Evidence Integrity 'Original' dimension.",
    )
    due_date: Optional[date] = None
    response_date: Optional[date] = None
    submit_date: Optional[date] = None
    msc: MSCSchema
    indication: IndicationSchema
    considerations: list[ConsiderationCreate] = Field(min_length=1)

    # Optional fields added by Layer 1's ownership tagger
    category: Optional[str] = None
    owner_team: Optional[str] = None


class RFIBatchCreate(BaseModel):
    records: list[RFICreate] = Field(min_length=1, max_length=500)


# ─── Outbound (read) schemas ───────────────────────────────────────────────────


class ConsiderationRead(BaseModel):
    id: uuid.UUID
    number: int
    consideration_id_str: Optional[str] = None
    concern_text: Optional[str] = None
    ctr_article_name: Optional[str] = None
    response_text: Optional[str] = None
    outcome_status: Optional[str] = None
    cluster_id: Optional[int] = None
    is_hub_article: Optional[bool] = None

    model_config = {"from_attributes": True}


class WorkflowStateRead(BaseModel):
    current_stage: str
    stage_entered_at: datetime
    sla_due_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RFIRead(BaseModel):
    id: uuid.UUID
    rfi_id: str
    rfi_type: Optional[str] = None
    status: Optional[str] = None
    source_document_ref: Optional[str] = None
    due_date: Optional[date] = None
    response_date: Optional[date] = None
    submit_date: Optional[date] = None
    received_at: datetime
    category: Optional[str] = None
    owner_team: Optional[str] = None
    nca_country: Optional[str] = None
    therapeutic_area_name: Optional[str] = None
    considerations: list[ConsiderationRead] = []
    workflow_state: Optional[WorkflowStateRead] = None

    model_config = {"from_attributes": True}


class BatchIngestResult(BaseModel):
    created: list[uuid.UUID]
    errors: list[dict]  # [{"rfi_id": str, "error": str}, ...]


# ─── Stage advancement ─────────────────────────────────────────────────────────


class StageAdvanceRequest(BaseModel):
    stage: str = Field(description=f"One of: {', '.join(VALID_STAGES)}")
    actor: Optional[str] = Field(
        default=None, description="Team or user advancing the stage."
    )
    notes: Optional[str] = Field(default=None, max_length=1000)


# ─── Audit ────────────────────────────────────────────────────────────────────


class AuditLogRead(BaseModel):
    id: uuid.UUID
    action: str
    actor: Optional[str] = None
    prev_hash: Optional[str] = None
    curr_hash: str
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditTrailRead(BaseModel):
    rfi_id: uuid.UUID
    entries: list[AuditLogRead]
    chain_valid: bool
