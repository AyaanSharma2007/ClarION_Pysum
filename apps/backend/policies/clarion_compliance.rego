package clarion.compliance

import future.keywords.in
import future.keywords.contains
import future.keywords.if

# RFI-SLA-001: Validation RFI response must be submitted within 10 calendar days
violation contains {"rule": "RFI-SLA-001", "record_id": rfi.rfi_id} if {
    some rfi in input.rfis
    rfi.rfi_type == "validation"
    rfi.status == "awaiting_response"
    
    ns_open := time.now_ns() - rfi.received_at_ns
    ns_open > 10 * 24 * 60 * 60 * 1000000000
}

# RFI-SLA-002: Assessment RFI response must be submitted within 12 calendar days
violation contains {"rule": "RFI-SLA-002", "record_id": rfi.rfi_id} if {
    some rfi in input.rfis
    rfi.rfi_type == "assessment"
    rfi.status == "awaiting_response"
    ns_open := time.now_ns() - rfi.received_at_ns
    ns_open > 12 * 24 * 60 * 60 * 1000000000
}

# FIELDS-001: A consideration cannot enter drafting until required fields are present
violation contains {"rule": "FIELDS-001", "record_id": consideration.consideration_id} if {
    some consideration in input.considerations
    consideration.status == "ready_for_response"
    missing := [f | f := ["concern_text", "ctr_article_id"][_]; not consideration[f]]
    count(missing) > 0
}
