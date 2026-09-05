package clarion.governance

import future.keywords.in
import future.keywords.contains
import future.keywords.if

# GATE-001: A response may not have a submitted_at timestamp without a recorded human approval event
deny contains {"rule": "GATE-001", "response_id": resp.id} if {
    some resp in input.responses
    resp.submitted_at
    not resp.approved_by
}

# ACCESS-001: A user may only write to RFI records owned by their team
deny contains {"rule": "ACCESS-001", "record_id": rfi.rfi_id} if {
    some rfi in input.rfis
    rfi.owner_team != input.request.user_team
    input.request.action == "write"
}
