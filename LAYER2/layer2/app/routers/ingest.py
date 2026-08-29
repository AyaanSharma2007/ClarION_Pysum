"""
Ingestion router — Layer 1's entry point into Layer 2.

Endpoints
---------
POST /rfi        — ingest one validated RFI record
POST /rfi/batch  — ingest up to 500 records in one call
GET  /rfi/{id}   — retrieve a full record by internal UUID
PATCH /rfi/{id}/stage — advance the workflow stage

The pipeline for each record:
  1. Upsert NCA (by country) + TherapeuticArea (by name)
  2. Upsert CTRArticle for each consideration (by name)
  3. Insert RFI row
  4. Insert Consideration rows
  5. Build rfi_text (concatenate response texts)
  6. Generate and store embedding
  7. Run extraction service (stub or Claude) → update category
  8. Create WorkflowState (stage=Received, SLA set)
  9. Write genesis AuditLog entry
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.audit import AuditLog, WorkflowState
from app.models.rfi import (
    CTRArticle,
    Consideration,
    NCA,
    RFI,
    TherapeuticArea,
)
from app.schemas.rfi import (
    AuditLogRead,
    AuditTrailRead,
    BatchIngestResult,
    RFIBatchCreate,
    RFICreate,
    RFIRead,
    ConsiderationRead,
    WorkflowStateRead,
    StageAdvanceRequest,
    VALID_STAGES,
)
from app.services.embedding import embedding_service
from app.services.extraction import extraction_service
from app.utils.audit import compute_hash, verify_chain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rfi", tags=["Ingestion"])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_rfi_text(considerations: list) -> str:
    """
    Build the text string we embed from all consideration concern + response texts.
    Including concern_text means semantic search can match against the reviewer's
    question, not just the sponsor's reply. Layer 5 benefits from this richer signal.
    """
    parts = []
    for c in considerations:
        concern = getattr(c, "concern_text", None) or ""
        response = (c.response.text if c.response else None) or ""
        if concern or response:
            block = f"Consideration {c.number}:"
            if concern:
                block += f"\nConcern: {concern}"
            if response:
                block += f"\nResponse: {response}"
            parts.append(block)
    return "\n\n".join(parts)


async def _upsert_nca(db: AsyncSession, country: str) -> NCA:
    """Get or create NCA by country (merge key)."""
    result = await db.execute(select(NCA).where(NCA.country == country))
    nca = result.scalar_one_or_none()
    if nca is None:
        nca = NCA(country=country)
        db.add(nca)
        await db.flush()
    return nca


async def _upsert_therapeutic_area(db: AsyncSession, name: str) -> TherapeuticArea:
    """Get or create TherapeuticArea by name (merge key)."""
    result = await db.execute(
        select(TherapeuticArea).where(TherapeuticArea.name == name)
    )
    ta = result.scalar_one_or_none()
    if ta is None:
        ta = TherapeuticArea(name=name)
        db.add(ta)
        await db.flush()
    return ta


async def _upsert_ctr_article(db: AsyncSession, name: str) -> CTRArticle:
    """Get or create CTRArticle by name (merge key)."""
    result = await db.execute(
        select(CTRArticle).where(CTRArticle.name == name)
    )
    article = result.scalar_one_or_none()
    if article is None:
        article = CTRArticle(name=name)
        db.add(article)
        await db.flush()
    return article


def _sla_due_at() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(
        hours=settings.SLA_HOURS_DEFAULT
    )


async def _ingest_one(db: AsyncSession, payload: RFICreate) -> RFI:
    """
    Core ingest pipeline for a single RFI record.
    Raises ValueError on duplicate rfi_id (idempotent — caller handles it).
    """
    # ── 0. Duplicate check ──────────────────────────────────────────────────
    existing = await db.execute(
        select(RFI).where(RFI.rfi_id == payload.rfi_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Duplicate rfi_id: {payload.rfi_id!r}")

    # ── 1. Upsert dimension tables ───────────────────────────────────────────
    nca = await _upsert_nca(db, payload.msc.country)
    ta = await _upsert_therapeutic_area(db, payload.indication.name)

    # ── 2. Build rfi_text for embedding ─────────────────────────────────────
    rfi_text = _build_rfi_text(payload.considerations)

    # ── 3. Generate embedding ────────────────────────────────────────────────
    embedding: Optional[list[float]] = None
    if rfi_text:
        try:
            embedding = await embedding_service.encode_async(rfi_text)
        except Exception as exc:
            logger.warning("Embedding failed for %s: %s", payload.rfi_id, exc)

    # ── 4. Run extraction service (may be stub) ──────────────────────────────
    category = payload.category  # Layer 1 may have pre-classified
    if not category and rfi_text:
        try:
            result = await extraction_service.extract(rfi_text)
            category = result.category
        except Exception as exc:
            logger.warning("Extraction failed for %s: %s", payload.rfi_id, exc)

    # ── 5. Insert RFI row ────────────────────────────────────────────────────
    rfi = RFI(
        rfi_id=payload.rfi_id,
        due_date=payload.due_date,
        response_date=payload.response_date,
        submit_date=payload.submit_date,
        category=category,
        owner_team=payload.owner_team,
        nca_id=nca.id,
        therapeutic_area_id=ta.id,
        rfi_text=rfi_text,
        embedding=embedding,
    )
    db.add(rfi)
    await db.flush()  # get rfi.id

    # ── 6. Insert Consideration rows ─────────────────────────────────────────────
    for c_payload in payload.considerations:
        article = await _upsert_ctr_article(db, c_payload.ctr_article.name)
        outcome_status = (
            c_payload.outcome.status if c_payload.outcome else None
        )

        # Build the Neo4j merge key — must match how load_rfi.py creates it.
        consideration_id_str = f"{payload.rfi_id}-C{c_payload.number}"

        # Embed the concern + response text for per-consideration ANN search.
        c_text = (
            f"{c_payload.concern_text or ''}".strip()
            + ("\n" + c_payload.response.text.strip() if c_payload.response.text else "")
        ).strip()
        c_embedding: Optional[list[float]] = None
        if c_text:
            try:
                c_embedding = await embedding_service.encode_async(c_text)
            except Exception as exc:
                logger.warning(
                    "Consideration embedding failed for %s-%s: %s",
                    payload.rfi_id, c_payload.number, exc,
                )

        consideration = Consideration(
            rfi_id=rfi.id,
            number=c_payload.number,
            consideration_id_str=consideration_id_str,
            concern_text=c_payload.concern_text,
            response_text=c_payload.response.text,
            embedding=c_embedding,
            outcome_status=outcome_status,
            ctr_article_id=article.id,
        )
        db.add(consideration)

    # ── 7. Initialise WorkflowState ──────────────────────────────────────────
    workflow = WorkflowState(
        rfi_id=rfi.id,
        current_stage="Received",
        stage_entered_at=datetime.now(tz=timezone.utc),
        sla_due_at=_sla_due_at(),
    )
    db.add(workflow)

    # ── 8. Write genesis AuditLog entry ─────────────────────────────────────
    audit_data = {
        "action": "ingested",
        "actor": payload.owner_team or "system",
        "metadata": {"rfi_id": payload.rfi_id, "stage": "Received"},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    curr_hash = compute_hash(None, audit_data)
    audit = AuditLog(
        rfi_id=rfi.id,
        action="ingested",
        actor=payload.owner_team or "system",
        prev_hash=None,
        curr_hash=curr_hash,
        # Store the full audit_data so verify_chain can recompute the hash exactly
        metadata_=audit_data,
    )
    db.add(audit)
    await db.flush()

    return rfi


def _to_rfi_read(rfi: RFI) -> RFIRead:
    """Map ORM RFI (with loaded relationships) to RFIRead schema."""
    considerations = [
        ConsiderationRead(
            id=c.id,
            number=c.number,
            concern_text=c.concern_text,
            ctr_article_name=c.ctr_article.name if c.ctr_article else None,
            response_text=c.response_text,
            outcome_status=c.outcome_status,
        )
        for c in (rfi.considerations or [])
    ]
    ws = None
    if rfi.workflow_state:
        ws = WorkflowStateRead(
            current_stage=rfi.workflow_state.current_stage,
            stage_entered_at=rfi.workflow_state.stage_entered_at,
            sla_due_at=rfi.workflow_state.sla_due_at,
        )
    return RFIRead(
        id=rfi.id,
        rfi_id=rfi.rfi_id,
        due_date=rfi.due_date,
        response_date=rfi.response_date,
        submit_date=rfi.submit_date,
        received_at=rfi.received_at,
        category=rfi.category,
        owner_team=rfi.owner_team,
        nca_country=rfi.nca.country if rfi.nca else None,
        therapeutic_area_name=(
            rfi.therapeutic_area.name if rfi.therapeutic_area else None
        ),
        considerations=considerations,
        workflow_state=ws,
    )


def _load_options():
    """Selectinload options for a fully-hydrated RFI query."""
    return [
        selectinload(RFI.nca),
        selectinload(RFI.therapeutic_area),
        selectinload(RFI.considerations).selectinload(Consideration.ctr_article),
        selectinload(RFI.workflow_state),
        selectinload(RFI.audit_logs),
    ]


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=RFIRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest one RFI record",
    description=(
        "Accepts a validated RFI payload (rfi_extraction_schema.json format), "
        "stores structured data + vector embedding, initialises workflow state, "
        "and writes the genesis audit log entry."
    ),
)
async def ingest_rfi(payload: RFICreate, db: AsyncSession = Depends(get_db)):
    try:
        rfi = await _ingest_one(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )

    # Re-query with relationships loaded for the response
    result = await db.execute(
        select(RFI).where(RFI.id == rfi.id).options(*_load_options())
    )
    rfi_full = result.scalar_one()
    return _to_rfi_read(rfi_full)


@router.post(
    "/batch",
    response_model=BatchIngestResult,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Ingest up to 500 RFI records in one call",
    description=(
        "Processes each record independently. Per-record errors are reported "
        "in the 'errors' list without aborting the whole batch."
    ),
)
async def ingest_rfi_batch(
    payload: RFIBatchCreate, db: AsyncSession = Depends(get_db)
):
    created: list[uuid.UUID] = []
    errors: list[dict] = []

    for record in payload.records:
        try:
            rfi = await _ingest_one(db, record)
            created.append(rfi.id)
        except ValueError as exc:
            errors.append({"rfi_id": record.rfi_id, "error": str(exc)})
        except Exception as exc:
            logger.exception("Unexpected error ingesting %s", record.rfi_id)
            errors.append(
                {"rfi_id": record.rfi_id, "error": f"Internal error: {exc}"}
            )

    return BatchIngestResult(created=created, errors=errors)


@router.get(
    "/{rfi_uuid}",
    response_model=RFIRead,
    summary="Retrieve a full RFI record by internal UUID",
)
async def get_rfi(rfi_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RFI).where(RFI.id == rfi_uuid).options(*_load_options())
    )
    rfi = result.scalar_one_or_none()
    if rfi is None:
        raise HTTPException(status_code=404, detail="RFI not found.")
    return _to_rfi_read(rfi)


@router.patch(
    "/{rfi_uuid}/stage",
    response_model=RFIRead,
    summary="Advance the workflow stage",
    description=(
        "Moves an RFI to the specified stage, resets the SLA timer, "
        "and appends a hash-chained audit log entry."
    ),
)
async def advance_stage(
    rfi_uuid: uuid.UUID,
    body: StageAdvanceRequest,
    db: AsyncSession = Depends(get_db),
):
    if body.stage not in VALID_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage {body.stage!r}. Valid stages: {VALID_STAGES}",
        )

    result = await db.execute(
        select(RFI).where(RFI.id == rfi_uuid).options(*_load_options())
    )
    rfi = result.scalar_one_or_none()
    if rfi is None:
        raise HTTPException(status_code=404, detail="RFI not found.")

    old_stage = rfi.workflow_state.current_stage if rfi.workflow_state else "Unknown"

    # Update WorkflowState
    rfi.workflow_state.current_stage = body.stage
    rfi.workflow_state.stage_entered_at = datetime.now(tz=timezone.utc)
    rfi.workflow_state.sla_due_at = _sla_due_at()

    # Hash-chain: find the last audit entry's hash
    last_hash: Optional[str] = None
    if rfi.audit_logs:
        last_hash = rfi.audit_logs[-1].curr_hash

    audit_data = {
        "action": "stage_advanced",
        "actor": body.actor or "system",
        "metadata": {
            "from_stage": old_stage,
            "to_stage": body.stage,
            "notes": body.notes,
        },
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    curr_hash = compute_hash(last_hash, audit_data)
    audit = AuditLog(
        rfi_id=rfi.id,
        action="stage_advanced",
        actor=body.actor or "system",
        prev_hash=last_hash,
        curr_hash=curr_hash,
        # Store the full audit_data so verify_chain can recompute the hash exactly
        metadata_=audit_data,
    )
    db.add(audit)

    await db.flush()
    await db.refresh(rfi, ["audit_logs", "workflow_state"])
    return _to_rfi_read(rfi)


@router.get(
    "/{rfi_uuid}/audit",
    response_model=AuditTrailRead,
    summary="Get the full tamper-evident audit trail for an RFI",
)
async def get_audit_trail(
    rfi_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(RFI).where(RFI.id == rfi_uuid).options(
            selectinload(RFI.audit_logs)
        )
    )
    rfi = result.scalar_one_or_none()
    if rfi is None:
        raise HTTPException(status_code=404, detail="RFI not found.")

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
        rfi_id=rfi_uuid, entries=entries, chain_valid=chain_valid
    )
