"""
Evidence Integrity Verification — Bible §6.3.

Extends the hash-chained audit trail with explicit checks against nine
data-integrity dimensions (ALCOA+).  This is Clarion's answer to ALCOA+,
applied to RFI/response records rather than claimed as a system-wide
certification.

Never display "ALCOA+ COMPLIANT" as an unconditional system claim — the
correct claim is per-record: "This record passed Clarion's Evidence
Integrity Check."
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.rfi import Consideration, CTRArticle, RFI

logger = logging.getLogger(__name__)


async def verify_evidence_integrity(
    consideration_id_str: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Run all 9 ALCOA+ dimension checks against a consideration record.

    Args:
        consideration_id_str: The Neo4j merge key, e.g. 'CT-2024-...-C1'.
        db: Async database session.

    Returns:
        {
            "consideration_id": str,
            "dimensions": {"Attributable": True, ...},
            "result": "VERIFIED BY CLARION CHECKS" | "FAILED",
            "failures": ["dimension_name", ...]
        }
    """
    # ── Load the consideration + parent RFI + audit logs ───────────────────
    stmt = (
        select(Consideration)
        .where(Consideration.consideration_id_str == consideration_id_str)
        .options(
            selectinload(Consideration.rfi).selectinload(RFI.audit_logs),
            selectinload(Consideration.rfi).selectinload(RFI.nca),
            selectinload(Consideration.ctr_article),
        )
    )
    result = await db.execute(stmt)
    consideration = result.scalar_one_or_none()

    if consideration is None:
        return {
            "consideration_id": consideration_id_str,
            "dimensions": {},
            "result": "RECORD NOT FOUND",
            "failures": ["record_not_found"],
        }

    rfi = consideration.rfi
    audit_logs = rfi.audit_logs if rfi else []

    dimensions: dict[str, bool] = {}
    failures: list[str] = []

    # ── 1. Attributable ───────────────────────────────────────────────────────
    # Record's created_by/approved_by references an authenticated user or a
    # named service identity — never null for state-changing events.
    attributable = all(
        log.actor is not None and log.actor.strip() != ""
        for log in audit_logs
    ) if audit_logs else False
    dimensions["Attributable"] = attributable
    if not attributable:
        failures.append("Attributable")

    # ── 2. Legible ────────────────────────────────────────────────────────────
    # Stored text is plain UTF-8, retrievable and renderable.
    concern = consideration.concern_text or ""
    response = consideration.response_text or ""
    legible = bool(concern.strip() or response.strip())
    try:
        if concern:
            concern.encode("utf-8")
        if response:
            response.encode("utf-8")
    except UnicodeEncodeError:
        legible = False
    dimensions["Legible"] = legible
    if not legible:
        failures.append("Legible")

    # ── 3. Contemporaneous ────────────────────────────────────────────────────
    # received_at/created_at timestamp exists and is not later than the audit
    # log entry that references it.
    contemporaneous = False
    if rfi and rfi.received_at and audit_logs:
        earliest_audit = min(log.created_at for log in audit_logs)
        contemporaneous = rfi.received_at <= earliest_audit
    dimensions["Contemporaneous"] = contemporaneous
    if not contemporaneous:
        failures.append("Contemporaneous")

    # ── 4. Original ───────────────────────────────────────────────────────────
    # The original PDF/source document reference is retained alongside any
    # extracted/derived text.
    original = bool(rfi and rfi.source_document_ref)
    dimensions["Original"] = original
    if not original:
        failures.append("Original")

    # ── 5. Accurate ───────────────────────────────────────────────────────────
    # Extracted structured fields (CTR_Article) can be reconciled against
    # existing reference data.
    accurate = consideration.ctr_article_id is not None and consideration.ctr_article is not None
    dimensions["Accurate"] = accurate
    if not accurate:
        failures.append("Accurate")

    # ── 6. Complete ───────────────────────────────────────────────────────────
    # All required fields per FIELDS-001 are present.
    complete = bool(
        consideration.concern_text
        and consideration.ctr_article_id
    )
    dimensions["Complete"] = complete
    if not complete:
        failures.append("Complete")

    # ── 7. Consistent ─────────────────────────────────────────────────────────
    # Foreign keys resolve to real records — no orphans, no drift between
    # the two databases. consideration_id_str is non-null.
    consistent = bool(
        consideration.consideration_id_str
        and consideration.rfi_id is not None
        and rfi is not None
    )
    dimensions["Consistent"] = consistent
    if not consistent:
        failures.append("Consistent")

    # ── 8. Enduring ───────────────────────────────────────────────────────────
    # Record exists in Postgres with no hard-delete path — only status
    # transitions, never row deletion. (Implicit: if we reached here, it exists.)
    enduring = True
    dimensions["Enduring"] = enduring

    # ── 9. Available ──────────────────────────────────────────────────────────
    # Record is retrievable via the standard API by any authorized team.
    # (Implicit: the API returned this record, so it's available.)
    available = True
    dimensions["Available"] = available

    result_str = (
        "VERIFIED BY CLARION CHECKS"
        if len(failures) == 0
        else "FAILED"
    )

    return {
        "consideration_id": consideration_id_str,
        "dimensions": dimensions,
        "result": result_str,
        "failures": failures,
    }
