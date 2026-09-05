from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import json

from ..opa_client import check_governance
from ..evidence_integrity import verify_evidence_integrity
from ..audit import write_audit_event

router = APIRouter(tags=["Governance"])

class ApprovalRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None

@router.post("/considerations/{consideration_id}/responses/{response_id}/approve")
async def approve_response(consideration_id: str, response_id: str, payload: ApprovalRequest):
    """
    Submission Gate API: Approves a drafted response. 
    This sets the 'approved_by' field, which satisfies GATE-001 for future submission.
    """
    
    # In a real implementation, we would fetch the current record from DB.
    # For now, we mock the record state pre and post approval.
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Mocking the updated response object
    updated_response = {
        "id": response_id,
        "consideration_id": consideration_id,
        "status": "approved",
        "approved_by": payload.approved_by,
        "approved_at": current_time,
        "submitted_at": None # Not submitted yet
    }
    
    # Run OPA check: Check if user can approve (ACCESS-001 equivalent could apply, 
    # but strictly checking GATE-001 when they try to submit)
    # If they immediately tried to submit, OPA GATE-001 would check `approved_by`
    governance_violations = check_governance(
        request={"action": "write", "user_team": "EU-Hub-Regulatory"},
        rfis=[{"rfi_id": "mock_rfi", "owner_team": "EU-Hub-Regulatory"}],
        responses=[updated_response]
    )
    
    if governance_violations:
        raise HTTPException(status_code=403, detail={"error": "Governance Violation", "violations": governance_violations})
        
    # Generate audit trail event
    audit_event = write_audit_event(
        record_id=response_id,
        record_type="response",
        event_type="approved",
        actor=payload.approved_by,
        payload={"notes": payload.notes},
        prev_hash=None # In reality, fetch latest curr_hash from DB
    )
    
    return {
        "status": "success",
        "message": f"Response {response_id} approved successfully.",
        "response": updated_response,
        "audit_event": audit_event
    }

@router.get("/considerations/{consideration_id}/evidence-integrity")
async def get_evidence_integrity(consideration_id: str):
    """
    Evaluates the 9-dimension evidence integrity for a consideration.
    """
    # Mock retrieving the full record
    mock_record = {
        "consideration_id": consideration_id,
        "rfi_id": f"RFI-{consideration_id.split('-')[0]}",
        "owner_team": "EU-Hub-Regulatory",
        "concern_text": "Sample concern text",
        "ctr_article_id": "art-123",
        "msc_id": "msc-456",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = verify_evidence_integrity(mock_record)
    return result
