"""
test_analytics.py — Unit tests for Analytics API endpoints and enrichment pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from apps.backend.app.api.analytics import router
from apps.backend.app.analytics_enrichment import (
    _validate_urgency,
    _default_analytics,
)

# Test validate urgency
def test_validate_urgency():
    assert _validate_urgency("high") == "High"
    assert _validate_urgency("MEDIUM") == "Medium"
    assert _validate_urgency("low ") == "Low"
    assert _validate_urgency("invalid") == "Medium"
    assert _validate_urgency(None) == "Medium"


# Test default analytics fallback
def test_default_analytics():
    res = _default_analytics()
    assert res["department"] == "Unknown"
    assert res["category"] == "General"
    assert res["urgency"] == "Medium"
    assert "summary" in res


# Test analytics endpoints router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("apps.backend.app.api.analytics._get_supabase")
def test_department_metrics_endpoint_no_supabase(mock_sb):
    mock_sb.return_value = None
    response = client.get("/analytics/department-metrics")
    assert response.status_code == 200
    data = response.json()
    assert "departments" in data
    assert data["departments"] == []


@patch("apps.backend.app.api.analytics._get_supabase")
def test_trends_endpoint_no_supabase(mock_sb):
    mock_sb.return_value = None
    response = client.get("/analytics/trends?days=30")
    assert response.status_code == 200
    data = response.json()
    assert "trends" in data
    assert data["trends"] == []


@patch("apps.backend.app.api.analytics._get_supabase")
def test_kpis_endpoint_no_supabase(mock_sb):
    mock_sb.return_value = None
    response = client.get("/analytics/kpis")
    assert response.status_code == 200
    data = response.json()
    assert data["total_this_month"] == 0
    assert data["most_problematic_department"] == "N/A"
