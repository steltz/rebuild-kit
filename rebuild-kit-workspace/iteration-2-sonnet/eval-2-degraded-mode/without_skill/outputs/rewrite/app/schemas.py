"""
Pydantic I/O models.

Field sets match ticketd/app/server.py's jsonify(dict(row)) output exactly
(same keys, same nullability) — see docs/01-LEGACY-BEHAVIOR-INVENTORY.md.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

# Legacy accepted BOTH string priorities ("low"/"med"/"high") and numeric
# strings ("1"/"2"/"3") — server.py:47-49, comment says both are actively
# sent by real clients. Preserved verbatim; not narrowed to an enum.
_PRIORITY_NUMERIC_MAP = {"1": "low", "2": "med", "3": "high"}
_VALID_PRIORITIES = {"low", "med", "high"}


class TicketOut(BaseModel):
    id: int
    title: str
    slug: str
    priority: str
    status: str
    assignee_id: Optional[int] = None
    created_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    title: str
    priority: str = "med"

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v) -> str:
        # Mirrors server.py:47-49 exactly, including coercing non-string
        # input (e.g. a JSON number) via str() first, the way the legacy
        # `str(body.get("priority", "med"))` did.
        s = str(v) if v is not None else "med"
        if s in _PRIORITY_NUMERIC_MAP:
            return _PRIORITY_NUMERIC_MAP[s]
        return s


class TicketCreateResponse(BaseModel):
    id: int
    slug: str


class TicketCloseResponse(BaseModel):
    closed: bool


class ResetRequest(BaseModel):
    email: str = ""


class ResetRequestResponse(BaseModel):
    ok: bool = True


class ResetConfirm(BaseModel):
    token: str = ""


class ResetConfirmResponse(BaseModel):
    ok: bool = True
    email: str
