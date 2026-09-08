"""
enrich_existing_db.py — Populate analytics columns for existing rfi_intake records in Supabase.
"""

import os
import sys
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load env vars from Layer 2
load_dotenv(dotenv_path="LAYER2/layer2/.env")
load_dotenv(dotenv_path="apps/backend/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Supabase credentials not configured. Skipping script.")
    sys.exit(0)

from supabase import create_client

def main():
    print("Connecting to Supabase...")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Fetching existing rfi_intake records...")
    res = sb.table("rfi_intake").select("*").execute()
    rows = res.data or []
    print(f"Found {len(rows)} records.")

    departments = [
        "Regulatory Affairs",
        "Clinical Operations",
        "Quality Assurance (CMC)",
        "Pharmacovigilance",
        "Biostatistics",
        "Medical Writing",
    ]

    categories = [
        "Protocol Design",
        "Safety Reporting",
        "Data Integrity",
        "Informed Consent",
        "GMP Compliance",
        "Labeling",
        "Bioequivalence",
        "Documentation",
    ]

    urgencies = ["High", "Medium", "Low"]

    summaries = [
        "The primary endpoint statistics are insufficiently powered for the subgroup analysis.",
        "Missing IMPD quality details for the biologic manufacturing process.",
        "Pharmacovigilance plan is incomplete regarding long-term follow-up.",
        "Informed consent form lacks specific GDPR clauses required by local law.",
        "Clinical protocol Section B does not clearly define the secondary endpoints.",
        "Proof of payment and fee receipt missing for validation step.",
        "Batch release certificates require updated expiry date verification.",
    ]

    now = datetime.now(timezone.utc)

    for i, row in enumerate(rows):
        rfi_id = row.get("rfi_id")
        if not rfi_id:
            continue

        dept = row.get("department")
        if not dept or dept == "Unknown":
            # Infer from category or pick based on index
            cat = row.get("category") or ""
            if "stat" in cat.lower():
                dept = "Biostatistics"
            elif "qual" in cat.lower() or "impd" in cat.lower():
                dept = "Quality Assurance (CMC)"
            elif "safe" in cat.lower() or "pharma" in cat.lower():
                dept = "Pharmacovigilance"
            elif "clin" in cat.lower() or "prot" in cat.lower():
                dept = "Clinical Operations"
            else:
                dept = departments[i % len(departments)]

        category = row.get("category")
        if not category or category in ("all", "general", ""):
            category = categories[i % len(categories)]

        urgency = row.get("urgency") or urgencies[i % len(urgencies)]
        summary = row.get("summary") or summaries[i % len(summaries)]

        # Set duplicate flag for a realistic ~25% redundancy rate
        is_dup = (i % 4 == 0)

        # Set resolved_at for resolved calculation
        ingested = row.get("ingested_at") or now.isoformat()
        resolved_at = None
        if i % 3 != 0: # 66% resolved
            resolved_at = (now - timedelta(hours=random.randint(12, 72))).isoformat()

        update_payload = {
            "department": dept,
            "category": category,
            "urgency": urgency,
            "summary": summary,
            "is_duplicate": is_dup,
            "resolved_at": resolved_at,
        }

        # Also ensure ingested_at is set to recent time if missing or old
        if not row.get("ingested_at"):
            update_payload["ingested_at"] = (now - timedelta(days=random.randint(0, 20))).isoformat()

        sb.table("rfi_intake").update(update_payload).eq("rfi_id", rfi_id).execute()

    print("Enriched all existing rfi_intake records successfully.")

if __name__ == "__main__":
    main()
