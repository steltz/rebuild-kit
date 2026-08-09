"""
ticketd — FastAPI + Postgres rewrite.

Endpoint-for-endpoint port of ticketd/app/server.py (Flask + SQLite), with
exactly two behavioral fixes applied, both named in the handover:

  1. Notification emails no longer block the request (transactional outbox,
     see app/services/notify.py + app/worker.py).
  2. Password-reset tokens are cryptographically random and hashed at rest,
     not MD5 (see app/services/tokens.py).

Everything else — including things that look like bugs — is preserved
verbatim because we have no production evidence (git history, access logs,
or a live DB) to say what's safe to change. See ../docs/ for the full
rationale, especially docs/00-EVIDENCE-AND-ASSUMPTIONS.md.
"""
from fastapi import FastAPI

from app.routers import auth, export, tickets

app = FastAPI(title="ticketd", version="0.1.0")

app.include_router(tickets.router)
app.include_router(auth.router)
app.include_router(export.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
