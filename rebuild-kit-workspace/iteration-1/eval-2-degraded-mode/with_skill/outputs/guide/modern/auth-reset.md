# auth-reset (designed-not-built)

Status: pending WO-006 (gated at M2). Same two endpoints, same limits (surviving-row rate
count with confirm-refund semantics — audit A-01), same non-disclosure wall. Changed:
CSPRNG tokens hashed at rest (ED-003), queued email (ED-002/ED-002b), bypass header behind
a default-ON config flag until OQ-004 is ruled. Purge policy narrowed per audit A-02.
