"""ticketd rewrite — FastAPI application factory.

Wire contract: rewrite/decisions/ADR-003-wire-compatibility.md.
No auth by design (legacy parity, Q1) — keep behind the same network boundary.
"""
from fastapi import FastAPI

from app.routers import auth, tickets

app = FastAPI(
    title="ticketd (rewrite)",
    # Legacy exposed no docs; keep the surface identical by default.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(tickets.router)
app.include_router(auth.router)


@app.get("/healthz")
def healthz():
    # New endpoint (not in legacy) — namespaced away from /api/* and /internal/*.
    return {"ok": True}
