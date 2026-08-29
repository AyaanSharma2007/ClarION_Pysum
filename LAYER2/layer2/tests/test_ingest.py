"""
Tests for the ingestion router.

Covers:
  - Single RFI ingest (happy path)
  - Duplicate detection (409)
  - Batch ingest with mixed valid/duplicate records
  - Workflow stage advancement
  - Audit trail chain validity
"""
from __future__ import annotations

import copy
import pytest
from httpx import AsyncClient

from tests.conftest import SAMPLE_RFI


@pytest.mark.asyncio
async def test_ingest_single_rfi(client: AsyncClient):
    """POST /rfi with the example payload returns 201 and a valid UUID."""
    resp = await client.post("/rfi", json=SAMPLE_RFI)
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert data["rfi_id"] == SAMPLE_RFI["rfi_id"]
    assert data["nca_country"] == "Germany"
    assert data["therapeutic_area_name"] == "Type 2 Diabetes Mellitus"
    assert len(data["considerations"]) == 1
    assert (
        data["considerations"][0]["ctr_article_name"]
        == "Part I - Regulatory / Annex I, Section 63"
    )
    assert "provide proof of payment" in data["considerations"][0]["concern_text"]
    assert data["workflow_state"]["current_stage"] == "Received"
    assert data["workflow_state"]["sla_due_at"] is not None
    # Embedding is not exposed in RFIRead — just check the record is stored
    assert "id" in data


@pytest.mark.asyncio
async def test_ingest_duplicate_returns_409(client: AsyncClient):
    """Posting the same rfi_id twice returns 409 Conflict."""
    # First insert (may already exist from previous test)
    await client.post("/rfi", json=SAMPLE_RFI)
    # Second insert — must fail
    resp = await client.post("/rfi", json=SAMPLE_RFI)
    assert resp.status_code == 409
    assert "Duplicate" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ingest_batch_mixed(client: AsyncClient):
    """
    Batch of 3 records: 2 new, 1 duplicate.
    Returns 207 with 2 created and 1 error.
    """
    new_a = {**SAMPLE_RFI, "rfi_id": "CT-BATCH-001"}
    new_b = {**SAMPLE_RFI, "rfi_id": "CT-BATCH-002"}
    dup = {**SAMPLE_RFI, "rfi_id": "CT-BATCH-001"}  # duplicate of new_a

    resp = await client.post("/rfi/batch", json={"records": [new_a, new_b, dup]})
    assert resp.status_code == 207, resp.text

    data = resp.json()
    assert len(data["created"]) == 2
    assert len(data["errors"]) == 1
    assert data["errors"][0]["rfi_id"] == "CT-BATCH-001"


@pytest.mark.asyncio
async def test_get_rfi_by_id(client: AsyncClient):
    """GET /rfi/{id} returns the full record."""
    # Insert
    ins = await client.post("/rfi", json={**SAMPLE_RFI, "rfi_id": "CT-GET-001"})
    assert ins.status_code == 201
    rfi_id = ins.json()["id"]

    # Retrieve
    resp = await client.get(f"/rfi/{rfi_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rfi_id


@pytest.mark.asyncio
async def test_get_rfi_not_found(client: AsyncClient):
    """GET /rfi/{nonexistent-uuid} returns 404."""
    resp = await client.get("/rfi/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_advance_stage(client: AsyncClient):
    """PATCH /rfi/{id}/stage advances stage and resets SLA."""
    ins = await client.post("/rfi", json={**SAMPLE_RFI, "rfi_id": "CT-STAGE-001"})
    assert ins.status_code == 201
    rfi_id = ins.json()["id"]
    old_sla = ins.json()["workflow_state"]["sla_due_at"]

    resp = await client.patch(
        f"/rfi/{rfi_id}/stage",
        json={"stage": "Categorized", "actor": "ml-pipeline", "notes": "Auto-classified"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflow_state"]["current_stage"] == "Categorized"
    # SLA should have been reset (different timestamp)
    assert data["workflow_state"]["sla_due_at"] != old_sla


@pytest.mark.asyncio
async def test_advance_stage_invalid(client: AsyncClient):
    """PATCH with an unknown stage name returns 400."""
    ins = await client.post("/rfi", json={**SAMPLE_RFI, "rfi_id": "CT-STAGE-INV"})
    rfi_id = ins.json()["id"]

    resp = await client.patch(
        f"/rfi/{rfi_id}/stage",
        json={"stage": "NotARealStage"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_audit_chain_valid(client: AsyncClient):
    """
    After ingest + 2 stage advances, GET /rfi/{id}/audit returns
    3 entries and chain_valid=True.
    """
    import uuid as _uuid
    unique_id = f"CT-AUDIT-{_uuid.uuid4().hex[:8].upper()}"
    ins = await client.post("/rfi", json={**SAMPLE_RFI, "rfi_id": unique_id})
    assert ins.status_code == 201, ins.text
    rfi_id = ins.json()["id"]

    await client.patch(f"/rfi/{rfi_id}/stage", json={"stage": "Categorized"})
    await client.patch(f"/rfi/{rfi_id}/stage", json={"stage": "RA_Clinical_Review"})

    resp = await client.get(f"/rfi/{rfi_id}/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 3
    assert data["chain_valid"] is True
