# Event/async payload schemas — empty, deliberately

P5 asks for JSON Schema files here for "events & async payloads." The legacy app has none: no
message queue, no webhooks emitted, no pub/sub, no background jobs — every interaction is a
synchronous HTTP request/response captured in `../openapi.yaml`.

This changes with WO-002 (async notification dispatch, PB-001): once ticket-close and
reset-request notifications move off the request thread, there will be an internal
notification/task payload worth schematizing here — but its shape depends on WO-002's FREE
mechanism choice (in-process task queue vs. a durable broker), which hasn't been made yet
(deliberately — that decision belongs to whoever implements WO-002, per `modern/CLAUDE.md`).
Add the schema here when that choice is made; this directory staying empty until then is
correct, not an oversight.
