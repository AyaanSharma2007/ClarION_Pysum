"""
consideration_api.py — Layer 2 endpoints for consideration detail & AI draft CRUD.

Endpoints
---------
GET  /rfi/consideration/{id}          — get consideration detail with RFI context
GET  /rfi/consideration/{id}/drafts   — list all AI draft responses
POST /rfi/consideration/{id}/drafts   — save a new AI draft response
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.rfi import (
    AIDraftResponse,
    Consideration,
    RFI,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Consideration API"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ConsiderationDetailRead(BaseModel):
    id: str
    number: int
    concern_text: Optional[str] = None
    response_text: Optional[str] = None
    ctr_article_name: Optional[str] = None
    rfi_id: str
    country: Optional[str] = None
    indication: Optional[str] = None

    model_config = {"from_attributes": True}


class DraftCreateRequest(BaseModel):
    consideration_id: str
    draft_text: str = Field(min_length=1)
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class DraftRead(BaseModel):
    id: str
    draft_text: str
    risk_score: Optional[float] = None
    created_at: str

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/rfi/consideration/{consideration_id}",
    response_model=ConsiderationDetailRead,
    summary="Get consideration detail with RFI context",
)
async def get_consideration_detail(
    consideration_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single consideration with its parent RFI context (country, indication)."""
    try:
        cid = uuid.UUID(consideration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    stmt = (
        select(Consideration)
        .options(
            selectinload(Consideration.rfi).selectinload(RFI.nca),
            selectinload(Consideration.rfi).selectinload(RFI.therapeutic_area),
            selectinload(Consideration.ctr_article),
        )
        .where(Consideration.id == cid)
    )
    result = await db.execute(stmt)
    consideration = result.scalar_one_or_none()

    if not consideration:
        raise HTTPException(status_code=404, detail="Consideration not found.")

    rfi = consideration.rfi
    return ConsiderationDetailRead(
        id=str(consideration.id),
        number=consideration.number,
        concern_text=consideration.concern_text,
        response_text=consideration.response_text,
        ctr_article_name=consideration.ctr_article.name if consideration.ctr_article else None,
        rfi_id=rfi.rfi_id if rfi else "",
        country=rfi.nca.country if rfi and rfi.nca else None,
        indication=rfi.therapeutic_area.name if rfi and rfi.therapeutic_area else None,
    )


@router.get(
    "/rfi/consideration/{consideration_id}/drafts",
    response_model=list[DraftRead],
    summary="List all AI draft responses for a consideration",
)
async def list_drafts(
    consideration_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return all historical AI-drafted responses ordered by creation time."""
    try:
        cid = uuid.UUID(consideration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    stmt = (
        select(AIDraftResponse)
        .where(AIDraftResponse.consideration_id == cid)
        .order_by(AIDraftResponse.created_at)
    )
    result = await db.execute(stmt)
    drafts = result.scalars().all()

    return [
        DraftRead(
            id=str(d.id),
            draft_text=d.draft_text,
            risk_score=d.risk_score,
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in drafts
    ]


@router.post(
    "/rfi/consideration/{consideration_id}/drafts",
    response_model=DraftRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new AI draft response",
)
async def create_draft(
    consideration_id: str,
    body: DraftCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Persist a new AI-drafted response and its risk score."""
    try:
        cid = uuid.UUID(consideration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    # Verify consideration exists
    stmt = select(Consideration).where(Consideration.id == cid)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Consideration not found.")

    draft = AIDraftResponse(
        consideration_id=cid,
        draft_text=body.draft_text,
        risk_score=body.risk_score,
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)

    return DraftRead(
        id=str(draft.id),
        draft_text=draft.draft_text,
        risk_score=draft.risk_score,
        created_at=draft.created_at.isoformat() if draft.created_at else "",
    )
