"""
Synchronize workflow stages for all RFIs in Layer 2 PostgreSQL database.
Marks resolved RFIs as 'submitted' with approval audit metadata,
and pending RFIs as 'awaiting_response'.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Load Layer 2 environment
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "LAYER2", "layer2", ".env"))
from LAYER2.layer2.app.database import AsyncSessionLocal
from scripts.seed_realistic_rfis import REALISTIC_RFIS

async def main():
    print("Updating RFI workflow stages in Layer 2 database...")
    now = datetime.now(timezone.utc)
    
    rfi_map = {r["rfi_id"]: r for r in REALISTIC_RFIS}
    
    async with AsyncSessionLocal() as session:
        # Fetch all RFIs
        res = await session.execute(text("SELECT id, rfi_id FROM rfi"))
        rows = res.fetchall()
        print(f"Found {len(rows)} RFIs in Layer 2 database.")
        
        updated_resolved = 0
        updated_pending = 0
        
        for rfi_uuid, rfi_id in rows:
            meta = rfi_map.get(rfi_id)
            if meta and meta.get("resolved_days_later"):
                # Resolved RFI -> Stage: submitted
                resolved_days_ago = meta["days_ago"] - meta["resolved_days_later"]
                res_dt = now - timedelta(days=max(0, resolved_days_ago))
                res_date_str = res_dt.strftime("%Y-%m-%d")
                
                # 1. Update RFI status & response_date
                await session.execute(
                    text("""
                        UPDATE rfi 
                        SET status = 'submitted', response_date = :res_date
                        WHERE id = :rfi_uuid
                    """),
                    {"res_date": res_dt.date(), "rfi_uuid": rfi_uuid}
                )
                
                # 2. Update or insert WorkflowState
                await session.execute(
                    text("""
                        INSERT INTO workflow_state (rfi_id, current_stage, stage_entered_at, sla_due_at, approved_by, approved_at)
                        VALUES (:rfi_uuid, 'submitted', :res_dt, :res_dt, 'Dr. M. Weber (EU Hub Regulatory Lead)', :res_dt)
                        ON CONFLICT (rfi_id) DO UPDATE
                        SET current_stage = 'submitted',
                            stage_entered_at = :res_dt,
                            approved_by = 'Dr. M. Weber (EU Hub Regulatory Lead)',
                            approved_at = :res_dt
                    """),
                    {"rfi_uuid": rfi_uuid, "res_dt": res_dt}
                )
                updated_resolved += 1
            else:
                # Pending RFI -> Stage: awaiting_response
                await session.execute(
                    text("""
                        UPDATE rfi 
                        SET status = 'awaiting_response', response_date = NULL
                        WHERE id = :rfi_uuid
                    """),
                    {"rfi_uuid": rfi_uuid}
                )
                await session.execute(
                    text("""
                        INSERT INTO workflow_state (rfi_id, current_stage, stage_entered_at, sla_due_at, approved_by, approved_at)
                        VALUES (:rfi_uuid, 'awaiting_response', :now, :sla_due, NULL, NULL)
                        ON CONFLICT (rfi_id) DO UPDATE
                        SET current_stage = 'awaiting_response',
                            stage_entered_at = :now,
                            approved_by = NULL,
                            approved_at = NULL
                    """),
                    {"rfi_uuid": rfi_uuid, "now": now, "sla_due": now + timedelta(days=10)}
                )
                
                # Clear response_text on consideration so it is truly awaiting drafting
                await session.execute(
                    text("""
                        UPDATE consideration
                        SET response_text = NULL
                        WHERE rfi_id = :rfi_uuid
                    """),
                    {"rfi_uuid": rfi_uuid}
                )
                updated_pending += 1

        await session.commit()
        print(f"Successfully updated workflow states:")
        print(f"  - {updated_resolved} RFIs marked as 'submitted' (resolved)")
        print(f"  - {updated_pending} RFIs marked as 'awaiting_response' (pending)")

if __name__ == "__main__":
    asyncio.run(main())
