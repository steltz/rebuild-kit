# notifications (designed-not-built)

Status: pending WO-004 (design-gated). A dispatch seam replaces app/notify.py: durable
record inside the triggering transaction, async delivery, env-configured transport, real
MIME. Recommended mechanism: transactional outbox (final choice recorded in ledger
free_choices at the WO-004 gate).
