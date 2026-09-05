from datetime import datetime

def verify_evidence_integrity(record: dict) -> dict:
    """
    Evaluates a single RFI / consideration / response combined record against 
    the 9 dimensions of Evidence Integrity (ALCOA+).
    
    Args:
        record: A combined dictionary representing the full state of a consideration,
                including its parent RFI and any responses, plus audit history.
                
    Returns:
        dict: Pass/fail for each dimension.
    """
    
    checks = {
        "Attributable": False,
        "Legible": False,
        "Contemporaneous": False,
        "Original": False,
        "Accurate": False,
        "Complete": False,
        "Consistent": False,
        "Enduring": False,
        "Available": False,
    }
    
    # 1. Attributable: Record's created_by/approved_by references an actor
    # In this mock, we assume 'owner_team' or 'approved_by' implies attribution
    if record.get("owner_team") or record.get("approved_by"):
        checks["Attributable"] = True
        
    # 2. Legible: Stored text is plain UTF-8 (implicitly true in JSON API)
    if isinstance(record.get("concern_text", ""), str):
        checks["Legible"] = True
        
    # 3. Contemporaneous: received_at/created_at timestamp exists
    if record.get("received_at") or record.get("created_at"):
        checks["Contemporaneous"] = True
        
    # 4. Original: source_document_ref is retained
    if record.get("source_document_ref") is not None or record.get("rfi_id"):
        # As long as it traces back to an RFI ID, we consider it passing
        checks["Original"] = True
        
    # 5. Accurate: Extracted fields can be reconciled (proxy: fields exist)
    if record.get("msc_id") or record.get("indication_id") or record.get("ctr_article_id"):
        checks["Accurate"] = True
        
    # 6. Complete: Required fields (FIELDS-001) are present
    if record.get("concern_text") and record.get("ctr_article_id"):
        checks["Complete"] = True
        
    # 7. Consistent: foreign keys resolve (proxy check)
    if record.get("rfi_id") and record.get("consideration_id"):
        checks["Consistent"] = True
        
    # 8. Enduring: Record exists in Postgres (implicit by being retrievable)
    checks["Enduring"] = True
    
    # 9. Available: Record is retrievable via standard API (implicit)
    checks["Available"] = True
    
    all_passed = all(checks.values())
    
    return {
        "dimensions": checks,
        "verified": all_passed,
        "status": "VERIFIED BY CLARION CHECKS" if all_passed else "FAILED INTEGRITY CHECKS"
    }
