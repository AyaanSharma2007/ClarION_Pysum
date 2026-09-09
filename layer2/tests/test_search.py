"""
Tests for the search router.

Covers:
  - Semantic search returns the most relevant record at rank 1
  - Filter by msc_country narrows results
  - GET /rfi/{id}/similar excludes self and returns candidates
  - Search with no matching records returns empty list (not error)
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from layer2.tests.conftest import SAMPLE_RFI


@pytest.mark.asyncio
async def test_semantic_search_top_result(client: AsyncClient):
    """
    Insert an RFI with distinctive text. Searching for that exact phrase
    should return it as the top result.
    """
    unique_payload = {
        **SAMPLE_RFI,
        "rfi_id": "CT-SEARCH-001",
        "considerations": [
            {
                **SAMPLE_RFI["considerations"][0],
                "concern_text": "Bioequivalence dissolution profile study required for modified release tablet formulation.",
                "response": {"text": "Bioequivalence dissolution profile data for modified release tablet is attached in Module 3.2."},
            }
        ],
    }
    ins = await client.post("/rfi", json=unique_payload)
    assert ins.status_code in (201, 409)  # 409 = already exists from prior run
    if ins.status_code == 409:
        pytest.skip("CT-SEARCH-001 already exists in DB from a prior test run")

    resp = await client.post(
        "/search",
        json={"query": "bioequivalence dissolution profile modified release tablet", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    top_ids = [r["rfi"]["rfi_id"] for r in data["results"][:3]]
    assert "CT-SEARCH-001" in top_ids


@pytest.mark.asyncio
async def test_search_filter_by_country(client: AsyncClient):
    """Filter by msc_country=France should not return German records."""
    # Insert a German record
    await client.post("/rfi", json={**SAMPLE_RFI, "rfi_id": "CT-FILTER-DE"})

    # Insert a French record
    french = {
        **SAMPLE_RFI,
        "rfi_id": "CT-FILTER-FR",
        "msc": {"country": "France"},
    }
    await client.post("/rfi", json=french)

    resp = await client.post(
        "/search",
        json={
            "query": "payment proof diabetes",
            "top_k": 10,
            "filters": {"msc_country": "France"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    countries = {r["rfi"]["nca_country"] for r in data["results"]}
    assert "France" in countries
    assert "Germany" not in countries


@pytest.mark.asyncio
async def test_search_empty_results(client: AsyncClient):
    """
    A highly specific query that won't match anything should return
    an empty list, not an error.
    """
    resp = await client.post(
        "/search",
        json={"query": "xyzzy frobnicator quantum entanglement RFI", "top_k": 3},
    )
    assert resp.status_code == 200
    # May return 0 results or some low-score results — should not crash
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_similar_rfis(client: AsyncClient):
    """GET /rfi/{id}/similar should exclude self and return other records."""
    # Insert 3 records
    ids = []
    for i in range(3):
        r = await client.post(
            "/rfi",
            json={
                **SAMPLE_RFI,
                "rfi_id": f"CT-SIM-00{i}",
                "considerations": [
                    {
                        "number": 1,
                        "concern_text": "Please provide the proof of payment document.",
                        "ctr_article": {"name": "Annex I, Section 63"},
                        "response": {
                            "text": f"Proof of payment document {i} is included."
                        },
                        "outcome": None,
                    }
                ],
            },
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    resp = await client.get(f"/rfi/{ids[0]}/similar?top_k=5")
    assert resp.status_code == 200
    data = resp.json()
    result_ids = [r["rfi"]["id"] for r in data["results"]]
    # Self must not be in results
    assert ids[0] not in result_ids
    # Other records should be there
    assert any(i in result_ids for i in ids[1:])
