from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TicketOut(BaseModel):
    """Verbatim column set -- docs/contracts/openapi.yaml#/components/schemas/Ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    priority: str | None
    status: str
    assignee_id: int | None
    created_at: datetime
    closed_at: datetime | None


class CreateTicketResponse(BaseModel):
    id: int
    slug: str
