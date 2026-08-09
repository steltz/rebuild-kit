# tickets (designed-not-built)

Status: pending WO-001 (skeleton + list), WO-002 (get), WO-003 (create), WO-005 (close).
FastAPI routers over Postgres; response surface byte-compatible with legacy per
docs/contracts/openapi.yaml — including the 200-{} quirk and priority aliases. Sanctioned
differences: 422s for legacy's garbage-input 500s (ED-004a/b), queued close notification
(ED-001), UTC timestamps internally (surface normalized by diff rules). As-built notes will
replace this stub as milestones close.
