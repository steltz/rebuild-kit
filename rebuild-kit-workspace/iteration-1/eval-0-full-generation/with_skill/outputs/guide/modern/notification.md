# notification (designed-not-built)

<!-- Status: designed-not-built. Built inside WO-004; reused by WO-005. -->

As designed: a `mail_outbox` table written in the same transaction as the triggering state
change, plus a worker delivering to SMTP with retry (at-least-once). Same sender, same
recipients, same headerless body format as legacy (mail-message.schema.json). Requests
never touch SMTP (NFR-1); the June-outage failure mode becomes "mail is delayed", never
"tickets can't close".

Mechanism choice is a recorded FREE default — the team can redirect it (existing queue
infra?) via OQ-004 before WO-004 starts.
