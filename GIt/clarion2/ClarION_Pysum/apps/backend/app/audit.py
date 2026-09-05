import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def generate_hash(body_json: str) -> str:
    return hashlib.sha256(body_json.encode('utf-8')).hexdigest()

def write_audit_event(
    record_id: str,
    record_type: str,
    event_type: str,
    actor: str,
    payload: dict,
    prev_hash: Optional[str]
) -> dict:
    """
    Creates a hash-chained audit event.
    """
    if not actor:
        raise ValueError("Actor cannot be null for an audit event.")
        
    body_dict = {
        "record_id": record_id,
        "record_type": record_type,
        "event_type": event_type,
        "actor": actor,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    
    # Sort keys to ensure deterministic hashing
    body_json = json.dumps(body_dict, sort_keys=True)
    curr_hash = generate_hash(body_json)
    
    audit_record = {
        "record_id": record_id,
        "record_type": record_type,
        "event_type": event_type,
        "actor": actor,
        "prev_hash": prev_hash,
        "curr_hash": curr_hash
    }
    
    logger.info(f"Generated audit event for {record_type} {record_id} ({event_type}): {curr_hash}")
    return audit_record

def verify_audit_chain(events: list) -> bool:
    """
    Verifies the hash chain of a list of audit events.
    Events must be ordered chronologically.
    """
    expected_prev = None
    for event in events:
        if event.get("prev_hash") != expected_prev:
            return False
            
        body_dict = {
            "record_id": event["record_id"],
            "record_type": event["record_type"],
            "event_type": event["event_type"],
            "actor": event["actor"],
            "payload": event.get("payload", {}),
            "prev_hash": event.get("prev_hash")
        }
        
        body_json = json.dumps(body_dict, sort_keys=True)
        recomputed_hash = generate_hash(body_json)
        
        if recomputed_hash != event["curr_hash"]:
            return False
            
        expected_prev = event["curr_hash"]
        
    return True
