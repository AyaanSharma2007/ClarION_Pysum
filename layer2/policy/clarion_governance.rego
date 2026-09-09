package clarion.governance

# GATE-001: A response may not have a submitted_at timestamp without a recorded human approval event
# Source: Clarion design invariant (Bible §0, §6.4) — no regulation permits automated submission
deny[{"rule": "GATE-001", "response_id": resp.id}] {
    resp := input.responses[_]
    resp.submitted_at
    not resp.approved_by
}

# ACCESS-001: A user may only write to RFI records owned by their team
# Source: Bible §6.1 — deterministic RLS policy
deny[{"rule": "ACCESS-001", "record_id": rfi.rfi_id}] {
    rfi := input.rfis[_]
    rfi.owner_team != input.request.user_team
    input.request.action == "write"
}
