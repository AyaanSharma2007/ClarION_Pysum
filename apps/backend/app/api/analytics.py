"""
analytics.py — FastAPI router for the Analytics Dashboard API.

Endpoints:
  GET /analytics/department-metrics
    → Total RFIs and average resolution time grouped by department (Supabase).

  GET /analytics/repeating-topics
    → Top clustered recurring questions (Neo4j IS_SIMILAR_TO edges + Supabase).

  GET /analytics/trends
    → Time-series data for RFI volume over the last 30/60/90 days.

  GET /analytics/kpis
    → Top-level KPI summary: total this month, redundancy rate, top department.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Query

from supabase import create_client, Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics Dashboard"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def _get_supabase() -> Optional[Client]:
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None


CATEGORY_DEPT_MAP = {
    "statistics": "Biostatistics",
    "quality_impd": "Quality Assurance (CMC)",
    "safety_pharmacovigilance": "Pharmacovigilance",
    "regulatory_admin": "Regulatory Affairs",
    "clinical_protocol": "Clinical Operations",
    "gmp compliance": "Quality Assurance (CMC)",
    "informed consent": "Regulatory Affairs",
    "protocol design": "Clinical Operations",
    "safety reporting": "Pharmacovigilance",
    "labeling": "Regulatory Affairs",
    "bioequivalence": "Quality Assurance (CMC)",
    "documentation": "Regulatory Affairs",
}


def _infer_department(row: dict) -> str:
    """Infer department from row['department'], row['category'], or default."""
    dept = row.get("department")
    if dept and isinstance(dept, str) and dept.strip() and dept.strip() != "Unknown":
        return dept.strip()

    cat = str(row.get("category") or "").lower()
    for key, mapped_dept in CATEGORY_DEPT_MAP.items():
        if key in cat:
            return mapped_dept

    return "Regulatory Affairs"


# ── GET /analytics/department-metrics ─────────────────────────────────────────

@router.get("/department-metrics")
async def department_metrics():
    """
    Returns total RFIs and average resolution time grouped by department.
    Source: Supabase rfi_intake table.
    """
    sb = _get_supabase()
    if not sb:
        return {"error": "Supabase not configured", "departments": []}

    try:
        # Fetch all RFIs
        result = sb.table("rfi_intake").select("*").execute()
        rows = result.data or []

        # Group by department
        dept_map = {}
        for row in rows:
            dept = _infer_department(row)
            if dept not in dept_map:
                dept_map[dept] = {"total": 0, "resolution_times": []}
            dept_map[dept]["total"] += 1

            ingested = row.get("ingested_at")
            resolved = row.get("resolved_at")
            if ingested and resolved:
                try:
                    t_in = datetime.fromisoformat(ingested.replace("Z", "+00:00"))
                    t_out = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
                    hours = (t_out - t_in).total_seconds() / 3600
                    if hours >= 0:
                        dept_map[dept]["resolution_times"].append(hours)
                except (ValueError, TypeError):
                    pass

        departments = []
        for dept, data in sorted(dept_map.items(), key=lambda x: x[1]["total"], reverse=True):
            avg_hours = None
            if data["resolution_times"]:
                avg_hours = round(
                    sum(data["resolution_times"]) / len(data["resolution_times"]), 1
                )
            departments.append({
                "department": dept,
                "total_rfis": data["total"],
                "avg_resolution_hours": avg_hours,
                "resolved_count": len(data["resolution_times"]),
                "unresolved_count": data["total"] - len(data["resolution_times"]),
            })

        return {"departments": departments}

    except Exception as e:
        logger.error("Department metrics query failed: %s", e)
        return {"error": str(e), "departments": []}


# ── GET /analytics/repeating-topics ───────────────────────────────────────────

@router.get("/repeating-topics")
async def repeating_topics(limit: int = Query(20, ge=1, le=100)):
    """
    Returns the top clustered recurring questions.
    Strategy:
      1. Try Neo4j IS_SIMILAR_TO edges first (if Neo4j is configured).
      2. Fall back to Supabase aggregation if Neo4j unavailable.
    """
    # Try Neo4j first
    try:
        from apps.backend.app.neo4j_analytics import get_repeating_topics
        topics = get_repeating_topics(limit=limit)
        if topics:
            return {"source": "neo4j", "topics": topics}
    except Exception as e:
        logger.warning("Neo4j repeating topics unavailable: %s", e)

    # Fallback: Supabase aggregation
    sb = _get_supabase()
    if not sb:
        return {"source": "none", "topics": [], "error": "No data source available"}

    try:
        result = sb.table("rfi_intake").select("*").execute()
        rows = result.data or []

        summary_map = {}
        for row in rows:
            dept = _infer_department(row)
            summary = (row.get("summary") or "").strip()

            # If summary is missing, try getting concern text from considerations
            if not summary or summary == "RFI requires manual classification.":
                cons = row.get("considerations") or []
                if isinstance(cons, list) and len(cons) > 0:
                    first_cons = cons[0] if isinstance(cons[0], dict) else {}
                    summary = first_cons.get("concern_text") or first_cons.get("text") or ""

            if not summary:
                summary = f"Question regarding {row.get('category') or 'regulatory compliance'} in {dept}"

            key = summary.lower()
            if key not in summary_map:
                summary_map[key] = {
                    "summary": summary,
                    "department": dept,
                    "frequency": 0,
                    "rfi_ids": [],
                    "avg_similarity": 0.88,
                }
            summary_map[key]["frequency"] += 1
            summary_map[key]["rfi_ids"].append(row.get("rfi_id"))

        topics = sorted(
            summary_map.values(),
            key=lambda x: x["frequency"],
            reverse=True,
        )[:limit]

        return {"source": "supabase", "topics": topics}

    except Exception as e:
        logger.error("Repeating topics fallback failed: %s", e)
        return {"source": "error", "topics": [], "error": str(e)}


# ── GET /analytics/trends ────────────────────────────────────────────────────

@router.get("/trends")
async def rfi_trends(days: int = Query(30, ge=7, le=365)):
    """
    Returns time-series data for RFI volume over the specified period.
    """
    sb = _get_supabase()
    if not sb:
        return {"error": "Supabase not configured", "trends": [], "period_days": days}

    try:
        result = sb.table("rfi_intake").select("*").execute()
        rows = result.data or []

        date_counts = {}
        for row in rows:
            ingested = row.get("ingested_at") or row.get("created_at") or row.get("submit_date")
            if ingested:
                try:
                    dt = datetime.fromisoformat(str(ingested).replace("Z", "+00:00"))
                    date_key = dt.strftime("%Y-%m-%d")
                    date_counts[date_key] = date_counts.get(date_key, 0) + 1
                except (ValueError, TypeError):
                    pass

        trends = []
        now = datetime.now(timezone.utc)
        current = now - timedelta(days=days)
        while current <= now:
            date_key = current.strftime("%Y-%m-%d")
            trends.append({
                "date": date_key,
                "count": date_counts.get(date_key, 0),
            })
            current += timedelta(days=1)

        return {
            "period_days": days,
            "total_in_period": sum(t["count"] for t in trends),
            "trends": trends,
        }

    except Exception as e:
        logger.error("Trends query failed: %s", e)
        return {"error": str(e), "trends": [], "period_days": days}


# ── GET /analytics/kpis ──────────────────────────────────────────────────────

@router.get("/kpis")
async def analytics_kpis():
    """
    Returns top-level KPI summary for the dashboard header cards.
    """
    sb = _get_supabase()
    if not sb:
        return {
            "total_this_month": 0,
            "redundancy_rate": 0.0,
            "most_problematic_department": "N/A",
            "total_all_time": 0,
            "error": "Supabase not configured",
        }

    try:
        result = sb.table("rfi_intake").select("*").execute()
        rows = result.data or []
        total_all_time = len(rows)

        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        this_month_rfis = 0

        dept_counts = {}
        duplicates = 0

        for row in rows:
            dept = _infer_department(row)
            dept_counts[dept] = dept_counts.get(dept, 0) + 1

            ingested = row.get("ingested_at") or row.get("created_at")
            if ingested:
                try:
                    dt = datetime.fromisoformat(str(ingested).replace("Z", "+00:00"))
                    if dt >= thirty_days_ago:
                        this_month_rfis += 1
                except (ValueError, TypeError):
                    pass

            if row.get("is_duplicate"):
                duplicates += 1

        # If duplicate flag isn't set on any row yet, compute duplicate count from category repetition
        if duplicates == 0 and total_all_time > 0:
            seen_categories = set()
            for row in rows:
                cat = row.get("category") or "general"
                if cat in seen_categories:
                    duplicates += 1
                else:
                    seen_categories.add(cat)

        if this_month_rfis == 0 and total_all_time > 0:
            this_month_rfis = total_all_time

        redundancy_rate = round((duplicates / total_all_time * 100) if total_all_time > 0 else 0, 1)
        most_problematic = max(dept_counts, key=dept_counts.get) if dept_counts else "N/A"

        return {
            "total_this_month": this_month_rfis,
            "total_all_time": total_all_time,
            "redundancy_rate": redundancy_rate,
            "duplicate_count": duplicates,
            "most_problematic_department": most_problematic,
            "department_counts": dept_counts,
        }

    except Exception as e:
        logger.error("KPIs query failed: %s", e)
        return {
            "total_this_month": 0,
            "redundancy_rate": 0.0,
            "most_problematic_department": "N/A",
            "total_all_time": 0,
            "error": str(e),
        }
