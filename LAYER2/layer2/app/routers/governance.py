"""
Governance router — Bible §6.3, §6.4, §7.1, §10, §14.1.

Endpoints
---------
POST /rfi/{rfi_id}/considerations       Add a consideration to an existing RFI
POST /considerations/{id}/responses     Attach a response to a consideration
POST /considerations/{id}/responses/{rid}/approve  Human approval (GATE-001)
POST /governance/policy-overrides       Record a justified policy override (§14.1)
POST /governance/advance-stage          Advance workflow via Event Dispatcher (§6.4, §10)
GET  /governance/policy-overrides/{record_id}  List overrides for a record
GET  /governance/transitions            List valid transitions from a given stage
GET  /considerations                    Batch hydration by IDs (Neo4j enrichment)
GET  /considerations/{id}/evidence-integrity  9-dimension ALCOA+ check
GET  /considerations/{id}/audit-trail   Hash-chained history for a consideration's RFI
GET  /rfi                               Structured filter (msc, owner_team, status)
GET  /rfi/export                        Bulk export for Neo4j graph-loading job
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from LAYER2.layer2.app.database import get_db
from LAYER2.layer2.app.models.audit import AuditLog, PolicyOverride, WorkflowState, ExtractionCorrection
from LAYER2.layer2.app.models.rfi import (
    CTRArticle,
    Consideration,
    NCA,
    RFI,
    TherapeuticArea,
)
from LAYER2.layer2.app.routers.ingest import _load_options, _to_rfi_read, _sla_due_at, _upsert_ctr_article
from LAYER2.layer2.app.schemas.rfi import (
    AuditLogRead,
    AuditTrailRead,
    ConsiderationRead,
    RFIRead,
    WorkflowStateRead,
)
from LAYER2.layer2.app.services.embedding import embedding_service
from LAYER2.layer2.app.services.event_dispatcher import (
    EventDispatchError,
    event_dispatcher,
    ALLOWED_TRANSITIONS,
)
from LAYER2.layer2.app.utils.audit import compute_hash, verify_chain
from LAYER2.layer2.app.utils.evidence_integrity import verify_evidence_integrity
from LAYER2.layer2.app.utils.safety_gateway import screen_untrusted_text

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Governance"])


# ─── Request/Response schemas for governance endpoints ────────────────────────


class ConsiderationAddRequest(BaseModel):
    """Add a consideration to an existing RFI (Bible §7.1)."""
    number: int = Field(ge=1)
    concern_text: str = Field(min_length=1)
    ctr_article_name: str = Field(min_length=1)
    response_text: Optional[str] = None


class ResponseAttachRequest(BaseModel):
    """Attach a response to a consideration (Bible §7.1)."""
    response_text: str = Field(min_length=1)


class ApprovalRequest(BaseModel):
    """Human approval action (Bible §6.4, GATE-001)."""
    approved_by: str = Field(min_length=1, description="Name or ID of the human approver.")


class EvidenceIntegrityResponse(BaseModel):
    """Response for the 9-dimension ALCOA+ check (Bible §6.3)."""
    consideration_id: str
    dimensions: dict[str, bool]
    result: str
    failures: list[str]


class RFIExportItem(BaseModel):
    """Lightweight export item for the Neo4j graph-loading job."""
    rfi_id: str
    rfi_type: Optional[str] = None
    msc_country: Optional[str] = None
    indication_name: Optional[str] = None
    considerations: list[dict]
    received_at: datetime


class PolicyOverrideRequest(BaseModel):
    """Record a justified policy override (Bible §14.1)."""
    policy_rule: str = Field(
        min_length=1,
        description="Rule being overridden, e.g. 'RFI-SLA-001'.",
    )
    record_id: str = Field(
        min_length=1,
        description="The rfi_id or consideration_id_str being exempted.",
    )
    record_type: str = Field(
        default="rfi",
        description="'rfi' or 'consideration'.",
    )
    overridden_by: str = Field(
        min_length=1,
        description="Human who authorised the override.",
    )
    justification: str = Field(
        min_length=10,
        description="Required justification — must be substantive, never empty.",
    )
    rfi_uuid: Optional[str] = Field(
        default=None,
        description="Optional parent RFI UUID for hash-chain linkage.",
    )


class PolicyOverrideResponse(BaseModel):
    """Response for a recorded policy override."""
    id: str
    policy_rule: str
    record_id: str
    record_type: str
    overridden_by: str
    justification: str
    overridden_at: str


class DispatchedStageAdvanceRequest(BaseModel):
    """Advance workflow via the Cross-Layer Event Dispatcher (Bible §6.4, §10)."""
    rfi_uuid: str = Field(description="Internal UUID of the RFI.")
    target_stage: str = Field(description="Target workflow stage.")
    actor: str = Field(min_length=1, description="User or team performing the transition.")
    notes: Optional[str] = Field(default=None, max_length=1000)


class TransitionMapResponse(BaseModel):
    """Valid transitions from a given stage."""
    current_stage: str
    allowed_transitions: list[str]


class OutcomeUpdateRequest(BaseModel):
    """Update regulatory outcome for a consideration (Bible §11)."""
    outcome_status: str = Field(description="accepted | follow-up-required | rejected")
    actor: str = Field(min_length=1, description="User recording the outcome.")


class ExtractionCorrectionRequest(BaseModel):
    """Log a human correction to an extracted field (Bible §14.1)."""
    field_name: str = Field(min_length=1, description="e.g. 'ctr_article_id', 'msc_id'")
    original_value: Optional[str] = None
    corrected_value: str = Field(min_length=1)
    corrected_by: str = Field(min_length=1)


class ExtractionCorrectionResponse(BaseModel):
    id: str
    consideration_id: str
    field_name: str
    original_value: Optional[str]
    corrected_value: str
    corrected_by: str
    corrected_at: str


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post(
    "/rfi/{rfi_id_str}/considerations",
    response_model=ConsiderationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a consideration to an existing RFI (Bible §7.1)",
)
async def add_consideration(
    rfi_id_str: str,
    body: ConsiderationAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a consideration; server computes and stores its embedding."""
    # Safety Gateway
    screen = screen_untrusted_text(body.concern_text + " " + (body.response_text or ""))
    if screen["flagged"]:
        raise HTTPException(
            status_code=422,
            detail=f"Safety Gateway: content quarantined. Matched: {screen['matched_patterns']}",
        )

    # Find the RFI by rfi_id (string identifier, not UUID)
    result = await db.execute(
        select(RFI).where(RFI.rfi_id == rfi_id_str).options(selectinload(RFI.audit_logs))
    )
    rfi = result.scalar_one_or_none()
    if rfi is None:
        raise HTTPException(status_code=404, detail=f"RFI {rfi_id_str!r} not found.")

    # Upsert CTR article
    article = await _upsert_ctr_article(db, body.ctr_article_name)

    # Build merge key
    consideration_id_str = f"{rfi_id_str}-C{body.number}"

    # Check for duplicate
    existing = await db.execute(
        select(Consideration).where(
            Consideration.consideration_id_str == consideration_id_str
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Consideration {consideration_id_str} already exists.",
        )

    # Embed concern_text + response_text
    c_text = body.concern_text.strip()
    if body.response_text:
        c_text += "\n" + body.response_text.strip()
    c_embedding: Optional[list[float]] = None
    try:
        c_embedding = await embedding_service.encode_async(c_text)
    except Exception as exc:
        logger.warning("Embedding failed for consideration %s: %s", consideration_id_str, exc)

    consideration = Consideration(
        rfi_id=rfi.id,
        number=body.number,
        consideration_id_str=consideration_id_str,
        concern_text=body.concern_text,
        response_text=body.response_text,
        embedding=c_embedding,
        ctr_article_id=article.id,
    )
    db.add(consideration)

    # Audit log
    last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
    audit_data = {
        "action": "consideration_added",
        "actor": "system",
        "metadata": {"consideration_id": consideration_id_str, "rfi_id": rfi_id_str},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    curr_hash = compute_hash(last_hash, audit_data)
    audit = AuditLog(
        rfi_id=rfi.id,
        action="consideration_added",
        actor="system",
        prev_hash=last_hash,
        curr_hash=curr_hash,
        metadata_=audit_data,
    )
    db.add(audit)
    await db.flush()

    return ConsiderationRead(
        id=consideration.id,
        number=consideration.number,
        consideration_id_str=consideration.consideration_id_str,
        concern_text=consideration.concern_text,
        ctr_article_name=body.ctr_article_name,
        response_text=consideration.response_text,
        outcome_status=None,
    )


@router.post(
    "/considerations/{consideration_id_str}/responses",
    status_code=status.HTTP_201_CREATED,
    summary="Attach a response to a consideration (Bible §7.1)",
)
async def attach_response(
    consideration_id_str: str,
    body: ResponseAttachRequest,
    db: AsyncSession = Depends(get_db),
):
    """Attach a response; server computes and stores its embedding."""
    # Safety Gateway
    screen = screen_untrusted_text(body.response_text)
    if screen["flagged"]:
        raise HTTPException(
            status_code=422,
            detail=f"Safety Gateway: content quarantined. Matched: {screen['matched_patterns']}",
        )

    result = await db.execute(
        select(Consideration).where(
            Consideration.consideration_id_str == consideration_id_str
        )
    )
    consideration = result.scalar_one_or_none()
    if consideration is None:
        raise HTTPException(
            status_code=404,
            detail=f"Consideration {consideration_id_str!r} not found.",
        )

    # Update response text
    consideration.response_text = body.response_text

    # Re-embed with updated response
    c_text = (consideration.concern_text or "").strip()
    if body.response_text:
        c_text += "\n" + body.response_text.strip()
    try:
        consideration.embedding = await embedding_service.encode_async(c_text)
    except Exception as exc:
        logger.warning("Re-embedding failed for %s: %s", consideration_id_str, exc)

    await db.flush()
    return {"status": "response_attached", "consideration_id": consideration_id_str}


@router.post(
    "/considerations/{consideration_id_str}/responses/{response_id}/approve",
    summary="Human approval action — writes approved_by, triggers GATE-001 check (Bible §6.4)",
)
async def approve_response(
    consideration_id_str: str,
    response_id: str,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Human approval action. Writes approved_by and approved_at to the
    parent RFI's WorkflowState, satisfying the GATE-001 precondition
    for the 'submitted' stage transition.
    """
    result = await db.execute(
        select(Consideration)
        .where(Consideration.consideration_id_str == consideration_id_str)
        .options(
            selectinload(Consideration.rfi)
            .selectinload(RFI.workflow_state),
            selectinload(Consideration.rfi)
            .selectinload(RFI.audit_logs),
        )
    )
    consideration = result.scalar_one_or_none()
    if consideration is None:
        raise HTTPException(status_code=404, detail="Consideration not found.")

    rfi = consideration.rfi
    if rfi is None or rfi.workflow_state is None:
        raise HTTPException(status_code=404, detail="Parent RFI or workflow state not found.")

    # Record approval
    now = datetime.now(tz=timezone.utc)
    rfi.workflow_state.approved_by = body.approved_by
    rfi.workflow_state.approved_at = now

    # Audit log
    last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
    audit_data = {
        "action": "response_approved",
        "actor": body.approved_by,
        "metadata": {
            "consideration_id": consideration_id_str,
            "approved_by": body.approved_by,
        },
        "created_at": now.isoformat(),
    }
    curr_hash = compute_hash(last_hash, audit_data)
    audit = AuditLog(
        rfi_id=rfi.id,
        action="response_approved",
        actor=body.approved_by,
        prev_hash=last_hash,
        curr_hash=curr_hash,
        metadata_=audit_data,
    )
    db.add(audit)
    await db.flush()

    return {
        "status": "approved",
        "approved_by": body.approved_by,
        "approved_at": now.isoformat(),
        "consideration_id": consideration_id_str,
    }


@router.get(
    "/considerations",
    response_model=list[ConsiderationRead],
    summary="Batch hydration by IDs — Neo4j enrichment results resolve through this (Bible §7.1)",
)
async def batch_hydrate_considerations(
    ids: str = Query(
        description="Comma-separated consideration_id_str values, e.g. 'CT-...-C1,CT-...-C2'"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Batch hydration endpoint for Neo4j enrichment."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        return []

    stmt = (
        select(Consideration)
        .where(Consideration.consideration_id_str.in_(id_list))
        .options(selectinload(Consideration.ctr_article))
    )
    result = await db.execute(stmt)
    considerations = result.scalars().all()

    return [
        ConsiderationRead(
            id=c.id,
            number=c.number,
            consideration_id_str=c.consideration_id_str,
            concern_text=c.concern_text,
            ctr_article_name=c.ctr_article.name if c.ctr_article else None,
            response_text=c.response_text,
            outcome_status=c.outcome_status,
            cluster_id=c.cluster_id,
            is_hub_article=c.is_hub_article,
        )
        for c in considerations
    ]


@router.get(
    "/rfi",
    response_model=list[RFIRead],
    summary="Structured filter — filter RFIs by msc, owner_team, status (Bible §7.1)",
)
async def filter_rfis(
    msc: Optional[str] = Query(default=None, description="Filter by MSC country"),
    owner_team: Optional[str] = Query(default=None, description="Filter by owner team"),
    rfi_status: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Structured filter — no vector search, pure SQL WHERE clauses."""
    stmt = select(RFI).options(*_load_options())

    if msc:
        stmt = stmt.join(NCA, RFI.nca_id == NCA.id).where(NCA.country == msc)
    if owner_team:
        stmt = stmt.where(RFI.owner_team == owner_team)
    if rfi_status:
        stmt = stmt.where(RFI.status == rfi_status)

    stmt = stmt.order_by(RFI.received_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rfis = result.scalars().unique().all()
    return [_to_rfi_read(rfi) for rfi in rfis]


@router.get(
    "/rfi/export",
    response_model=list[RFIExportItem],
    summary="Bulk export for Neo4j graph-loading job (Bible §7.1, §8.3)",
)
async def export_rfis(
    since: Optional[datetime] = Query(
        default=None, description="Export RFIs received on or after this timestamp"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Bulk export endpoint — feeds load_rfi.py for Neo4j graph sync."""
    stmt = (
        select(RFI)
        .options(
            selectinload(RFI.nca),
            selectinload(RFI.therapeutic_area),
            selectinload(RFI.considerations).selectinload(Consideration.ctr_article),
        )
        .order_by(RFI.received_at)
    )
    if since:
        stmt = stmt.where(RFI.received_at >= since)

    result = await db.execute(stmt)
    rfis = result.scalars().unique().all()

    items = []
    for rfi in rfis:
        considerations = []
        for c in (rfi.considerations or []):
            considerations.append({
                "consideration_id": c.consideration_id_str,
                "number": c.number,
                "concern_text": c.concern_text,
                "response_text": c.response_text,
                "ctr_article_name": c.ctr_article.name if c.ctr_article else None,
                "outcome_status": c.outcome_status,
            })
        items.append(RFIExportItem(
            rfi_id=rfi.rfi_id,
            rfi_type=rfi.rfi_type,
            msc_country=rfi.nca.country if rfi.nca else None,
            indication_name=rfi.therapeutic_area.name if rfi.therapeutic_area else None,
            considerations=considerations,
            received_at=rfi.received_at,
        ))
    return items


@router.get(
    "/considerations/{consideration_id_str}/evidence-integrity",
    response_model=EvidenceIntegrityResponse,
    summary="Evidence Integrity Check — 9 ALCOA+ dimensions (Bible §6.3)",
)
async def check_evidence_integrity(
    consideration_id_str: str,
    db: AsyncSession = Depends(get_db),
):
    """Run the 9-dimension evidence integrity check from Bible §6.3."""
    result = await verify_evidence_integrity(consideration_id_str, db)
    return EvidenceIntegrityResponse(**result)


@router.get(
    "/considerations/{consideration_id_str}/audit-trail",
    response_model=AuditTrailRead,
    summary="Hash-chained audit trail for a consideration's parent RFI (Bible §7.1)",
)
async def get_consideration_audit_trail(
    consideration_id_str: str,
    db: AsyncSession = Depends(get_db),
):
    """Full hash-chained history for the parent RFI of this consideration."""
    result = await db.execute(
        select(Consideration)
        .where(Consideration.consideration_id_str == consideration_id_str)
        .options(
            selectinload(Consideration.rfi).selectinload(RFI.audit_logs)
        )
    )
    consideration = result.scalar_one_or_none()
    if consideration is None:
        raise HTTPException(status_code=404, detail="Consideration not found.")

    rfi = consideration.rfi
    entries_raw = [
        {
            "curr_hash": e.curr_hash,
            "prev_hash": e.prev_hash,
            "action": e.action,
            "actor": e.actor,
            "metadata": e.metadata_,
            "created_at": e.created_at,
        }
        for e in rfi.audit_logs
    ]
    chain_valid = verify_chain(entries_raw)

    entries = [
        AuditLogRead(
            id=e.id,
            action=e.action,
            actor=e.actor,
            prev_hash=e.prev_hash,
            curr_hash=e.curr_hash,
            metadata=e.metadata_,
            created_at=e.created_at,
        )
        for e in rfi.audit_logs
    ]

    return AuditTrailRead(
        rfi_id=rfi.id, entries=entries, chain_valid=chain_valid
    )


# ─── Event Dispatcher + Policy Override endpoints (Layer 6) ──────────────────


@router.post(
    "/governance/advance-stage",
    summary="Advance workflow via the Cross-Layer Event Dispatcher (Bible §6.4, §10)",
    description=(
        "Validates the transition against the state machine, enforces GATE-001, "
        "writes a hash-chained audit event, syncs rfi.status, and fires any "
        "cross-layer side-effects — all in one atomic operation."
    ),
)
async def dispatched_advance_stage(
    body: DispatchedStageAdvanceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Advance via EventDispatcher — replaces ad-hoc stage-change logic."""
    try:
        result = await event_dispatcher.advance_stage(
            db=db,
            rfi_uuid=body.rfi_uuid,
            target_stage=body.target_stage,
            actor=body.actor,
            notes=body.notes,
        )
        return result
    except EventDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/governance/policy-overrides",
    response_model=PolicyOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a justified policy override (Bible §14.1)",
    description=(
        "Records a permanent, attributable override of a governance rule. "
        "The override row and a hash-chained audit event are written in a "
        "single transaction. The rule stays enforced for all other records."
    ),
)
async def create_policy_override(
    body: PolicyOverrideRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a policy override — creates both the override row and an audit event."""
    try:
        result = await event_dispatcher.record_policy_override(
            db=db,
            policy_rule=body.policy_rule,
            record_id=body.record_id,
            record_type=body.record_type,
            overridden_by=body.overridden_by,
            justification=body.justification,
            rfi_uuid=body.rfi_uuid,
        )
        return PolicyOverrideResponse(**result)
    except Exception as exc:
        logger.error("Policy override failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/governance/policy-overrides/{record_id}",
    response_model=list[PolicyOverrideResponse],
    summary="List all policy overrides for a record (Bible §14.1)",
)
async def list_policy_overrides(
    record_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return all policy overrides recorded for a given record_id."""
    overrides = await event_dispatcher.get_overrides_for_record(db, record_id)
    return [PolicyOverrideResponse(**o) for o in overrides]


@router.get(
    "/governance/transitions",
    response_model=TransitionMapResponse,
    summary="List valid transitions from a given stage (Bible §6.4)",
)
async def get_valid_transitions(
    current_stage: str = Query(description="Current workflow stage"),
):
    """Return the set of valid target stages from the given current stage."""
    allowed = ALLOWED_TRANSITIONS.get(current_stage, set())
    return TransitionMapResponse(
        current_stage=current_stage,
        allowed_transitions=sorted(allowed),
    )


@router.post(
    "/considerations/{id_str}/outcome",
    status_code=status.HTTP_200_OK,
    summary="Update regulatory outcome for a consideration (Layer 5)",
)
async def update_consideration_outcome(
    id_str: str,
    body: OutcomeUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record the final regulatory outcome of a consideration.
    Updates outcome_status and logs a hash-chained audit event.
    """
    result = await db.execute(
        select(Consideration)
        .where(Consideration.consideration_id_str == id_str)
        .options(selectinload(Consideration.rfi).selectinload(RFI.audit_logs))
    )
    consideration = result.scalar_one_or_none()
    if not consideration:
        raise HTTPException(status_code=404, detail="Consideration not found")

    old_status = consideration.outcome_status
    consideration.outcome_status = body.outcome_status

    # Audit log
    rfi = consideration.rfi
    last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
    audit_data = {
        "action": "outcome_updated",
        "actor": body.actor,
        "metadata": {
            "consideration_id": id_str,
            "old_status": old_status,
            "new_status": body.outcome_status,
        },
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    curr_hash = compute_hash(last_hash, audit_data)
    audit = AuditLog(
        rfi_id=rfi.id,
        action="outcome_updated",
        actor=body.actor,
        prev_hash=last_hash,
        curr_hash=curr_hash,
        metadata_=audit_data,
    )
    db.add(audit)
    await db.commit()

    return {"status": "ok", "consideration_id": id_str, "outcome_status": body.outcome_status}


@router.post(
    "/considerations/{id_str}/corrections",
    response_model=ExtractionCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log human correction to an extracted field (Bible §14.1)",
)
async def log_extraction_correction(
    id_str: str,
    body: ExtractionCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Records a correction to an automatically extracted field.
    Creates an ExtractionCorrection row for ML training and an AuditLog event.
    """
    result = await db.execute(
        select(Consideration)
        .where(Consideration.consideration_id_str == id_str)
        .options(selectinload(Consideration.rfi).selectinload(RFI.audit_logs))
    )
    consideration = result.scalar_one_or_none()
    if not consideration:
        raise HTTPException(status_code=404, detail="Consideration not found")

    correction = ExtractionCorrection(
        consideration_id=id_str,
        field_name=body.field_name,
        original_value=body.original_value,
        corrected_value=body.corrected_value,
        corrected_by=body.corrected_by,
    )
    db.add(correction)

    # Audit log
    rfi = consideration.rfi
    last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
    audit_data = {
        "action": "extraction_corrected",
        "actor": body.corrected_by,
        "metadata": {
            "consideration_id": id_str,
            "field_name": body.field_name,
            "original_value": body.original_value,
            "corrected_value": body.corrected_value,
        },
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    curr_hash = compute_hash(last_hash, audit_data)
    audit = AuditLog(
        rfi_id=rfi.id,
        action="extraction_corrected",
        actor=body.corrected_by,
        prev_hash=last_hash,
        curr_hash=curr_hash,
        metadata_=audit_data,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(correction)

    return ExtractionCorrectionResponse(
        id=str(correction.id),
        consideration_id=correction.consideration_id,
        field_name=correction.field_name,
        original_value=correction.original_value,
        corrected_value=correction.corrected_value,
        corrected_by=correction.corrected_by,
        corrected_at=correction.corrected_at.isoformat(),
    )


# ─── SimPy Simulation Engine (Bible §10, Phase C) ────────────────────────────


class SimulationRequest(BaseModel):
    """Parameters for the Monte Carlo simulation."""
    n_runs: int = Field(default=100, ge=1, le=1000, description="Number of Monte Carlo runs")
    horizon_days: int = Field(default=90, ge=7, le=365, description="Simulation horizon in days")
    sla_days: float = Field(default=10.0, ge=1, le=30, description="SLA deadline in days")


@router.post(
    "/governance/simulate",
    status_code=status.HTTP_200_OK,
    summary="Run Monte Carlo portfolio simulation (Bible §10, Phase C)",
    description=(
        "Runs a discrete-event Monte Carlo simulation using SimPy to forecast "
        "portfolio-level RFI volumes, SLA breach probabilities per MSC, and "
        "bottleneck identification. All outputs are probabilistic — never certainty."
    ),
)
async def run_simulation(body: SimulationRequest):
    from LAYER2.layer2.app.services.simulation import SimulationEngine

    try:
        engine = SimulationEngine(sla_days=body.sla_days)
        results = engine.run_simulation(
            n_runs=body.n_runs,
            horizon_days=body.horizon_days,
        )
    except Exception as exc:
        logger.error("Simulation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation error: {exc}",
        )

    return results
