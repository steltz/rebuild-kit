# Draft spec — subsystem: notifications (cross-cutting)

## Feature: outbound email — app/notify.py::send_mail

- statement: Two call sites total: ticket close (`app/server.py:76`) and reset request
  (`app/server.py:94`). No other notification exists (no assignment, no creation email).
  fidelity: FIXED (the trigger set — exactly these two events notify)   confidence: cited
  evidence: ticketd/app/server.py:76,94; inventory.json dependency_edges
- statement: Transport today: `smtplib.SMTP("smtp.internal", 25, timeout=30)`, envelope sender
  `ticketd@example.internal`, and the `body` string passed directly as message DATA — so the
  emails have **no headers at all** (no Subject, no From/To headers; just a raw body line).
  fidelity: FREE — mechanism. Outcomes required: (a) close notice reaches the watchers
  address with the ticket title; (b) reset mail reaches the requested address containing the
  presentable token. Modern chooses transport, sender identity, and proper MIME headers per
  modern/CLAUDE.md; the headerless-raw-body artifact is not ported (see do-not-port DNP-003).
  confidence: cited   evidence: ticketd/app/notify.py:5-7
- statement: Dispatch timing is synchronous inside request handlers with up to 30s blocking.
  fidelity: REPAIR — PB-001 (dispositioned per call site: ED-001 close, ED-002 reset).
  confidence: cited   evidence: ticketd/app/notify.py:1 (docstring: "~2s typical, 30s on
  provider trouble"), ticketd/app/notify.py:6
- statement: Hardcoded SMTP host/port; no configuration surface exists.
  fidelity: FREE — modern uses env config (modern/CLAUDE.md conventions).
  confidence: cited   evidence: ticketd/app/notify.py:6

## Harness note
For replay purposes emails are an observable side effect: both harness sides run against a
capturing SMTP stub (see verification/harness/), and each captured send is normalized to the
event shape in docs/contracts/schemas/email-dispatch.schema.json. ED-001/ED-002 assert
`mode: queued` on the modern side; content assertions (recipient, token/title inclusion)
apply to both sides.
