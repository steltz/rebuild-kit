import datetime

from pydantic import BaseModel, field_validator

# Legacy clients send priority as "1"/"2"/"3" or "low"/"med"/"high" — both
# must keep working (app/server.py:47 in the legacy source). Anything else
# is passed through unchanged, matching legacy: the DB CHECK constraint
# rejects it, not this layer (see ck_tickets_priority in models.py) — a
# deliberate parity choice, not an oversight. See docs/AUDIT.md.
_PRIORITY_ALIASES = {"1": "low", "2": "med", "3": "high"}


class TicketCreate(BaseModel):
    title: str
    priority: str = "med"

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: object) -> str:
        v = str(v)
        return _PRIORITY_ALIASES.get(v, v)


class TicketOut(BaseModel):
    id: int
    title: str
    slug: str
    priority: str
    status: str
    assignee_id: int | None
    created_at: datetime.datetime
    closed_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class TicketCreateOut(BaseModel):
    id: int
    slug: str


class CloseTicketOut(BaseModel):
    closed: bool


class ResetRequestIn(BaseModel):
    email: str


class ResetRequestOut(BaseModel):
    ok: bool = True


class ResetConfirmIn(BaseModel):
    token: str = ""


class ResetConfirmOut(BaseModel):
    ok: bool
    email: str | None = None
