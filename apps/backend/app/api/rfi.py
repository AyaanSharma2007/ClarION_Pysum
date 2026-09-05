from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from ..opa_client import check_compliance, check_governance
from ..audit import write_audit_event

router = APIRouter(tags=["Layer 2 - Central Repository"])

class RFI(BaseModel):
    rfi_type: str
    msc_id: str
    indication_id: str
    owner_team: str

class Consideration(BaseModel):
    concern_text: str
    ctr_article_id: Optional[str] = None

class Response(BaseModel):
    response_text: str

# Mock DB
mock_rfis = []
mock_considerations = []
mock_responses = []

@router.post("/rfi")
async def create_rfi(rfi: RFI):
    """Creates an RFI record."""
    rfi_id = str(uuid.uuid4())
    
    # Check governance (e.g., ACCESS-001)
    gov_violations = check_governance(
        request={"action": "write", "user_team": rfi.owner_team},
        rfis=[{"rfi_id": rfi_id, "owner_team": rfi.owner_team}],
        responses=[]
    )
    if gov_violations:
        raise HTTPException(status_code=403, detail={"violations": gov_violations})
        
    record = {
        "rfi_id": rfi_id,
        "rfi_type": rfi.rfi_type,
        "status": "received",
        "msc_id": rfi.msc_id,
        "indication_id": rfi.indication_id,
        "owner_team": rfi.owner_team,
        "received_at": datetime.now(timezone.utc).isoformat()
    }
    mock_rfis.append(record)
    
    # Audit log
    audit_event = write_audit_event(rfi_id, "rfi", "created", rfi.owner_team, record, None)
    
    return {"status": "created", "rfi_id": rfi_id, "audit_event": audit_event}

@router.post("/rfi/{rfi_id}/considerations")
async def add_consideration(rfi_id: str, consideration: Consideration):
    """Adds a consideration to an RFI."""
    # Build join key
    count = len([c for c in mock_considerations if c["rfi_id"] == rfi_id]) + 1
    consideration_id = f"{rfi_id}-C{count}"
    
    # Check compliance (FIELDS-001) if status moves to ready_for_response
    # For now it's just created, but we mock the check anyway
    comp_violations = check_compliance(
        rfis=[],
        considerations=[{
            "consideration_id": consideration_id, 
            "status": "ready_for_response", 
            "concern_text": consideration.concern_text, 
            "ctr_article_id": consideration.ctr_article_id
        }]
    )
    if comp_violations:
        raise HTTPException(status_code=400, detail={"violations": comp_violations})
        
    record = {
        "consideration_id": consideration_id,
        "rfi_id": rfi_id,
        "concern_text": consideration.concern_text,
        "ctr_article_id": consideration.ctr_article_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # Normally we would embed it here via a call to local LLM
    mock_considerations.append(record)
    
    audit_event = write_audit_event(consideration_id, "consideration", "created", "System", record, None)
    
    return {"status": "created", "consideration_id": consideration_id, "audit_event": audit_event}

@router.post("/considerations/{consideration_id}/responses")
async def add_response(consideration_id: str, response: Response):
    """Adds a drafted response to a consideration."""
    response_id = str(uuid.uuid4())
    
    record = {
        "id": response_id,
        "consideration_id": consideration_id,
        "response_text": response.response_text,
        "approved_by": None,
        "submitted_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    mock_responses.append(record)
    
    audit_event = write_audit_event(response_id, "response", "drafted", "User", record, None)
    
    return {"status": "created", "response_id": response_id, "audit_event": audit_event}

@router.get("/rfi/{rfi_id}")
async def get_rfi(rfi_id: str):
    """Fetches a full RFI record."""
    rfi = next((r for r in mock_rfis if r["rfi_id"] == rfi_id), None)
    if not rfi:
        raise HTTPException(status_code=404, detail="RFI not found")
        
    considerations = [c for c in mock_considerations if c["rfi_id"] == rfi_id]
    for c in considerations:
        c["responses"] = [r for r in mock_responses if r["consideration_id"] == c["consideration_id"]]
        
    return {"rfi": rfi, "considerations": considerations}

@router.get("/considerations")
async def get_considerations_batch(ids: str = Query(..., description="Comma separated consideration_ids")):
    """Batch hydration for considerations."""
    id_list = ids.split(",")
    return [c for c in mock_considerations if c["consideration_id"] in id_list]
