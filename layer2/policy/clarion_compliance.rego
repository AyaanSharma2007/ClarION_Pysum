package clarion.compliance

# RFI-SLA-001: Validation RFI response must be submitted within 10 calendar days
# Source: EU CTR 536/2014, validation phase response window (Bible §1.1, §6.1)
violation[{"rule": "RFI-SLA-001", "record_id": rfi.rfi_id}] {
    rfi := input.rfis[_]
    rfi.rfi_type == "validation"
    rfi.status == "awaiting_response"
    days_open := time.diff_days(time.now_ns(), rfi.received_at_ns)
    days_open > 10
}

# RFI-SLA-002: Assessment RFI response must be submitted within 12 calendar days
# Source: EU CTR 536/2014, assessment phase response window (Bible §6.1)
violation[{"rule": "RFI-SLA-002", "record_id": rfi.rfi_id}] {
    rfi := input.rfis[_]
    rfi.rfi_type == "assessment"
    rfi.status == "awaiting_response"
    days_open := time.diff_days(time.now_ns(), rfi.received_at_ns)
    days_open > 12
}

# FIELDS-001: A consideration cannot enter drafting until required fields are present
# Source: Bible §6.1 — concern_text and ctr_article_id must be non-null
violation[{"rule": "FIELDS-001", "record_id": consideration.consideration_id}] {
    consideration := input.considerations[_]
    consideration.status == "ready_for_response"
    missing := [f | f := ["concern_text", "ctr_article_id"][_]; not consideration[f]]
    count(missing) > 0
}
