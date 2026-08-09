"""Wire-compat helpers (ADR-003). Legacy quirk numbers per inventory/behavior-inventory.md."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import Request

from app.config import settings
from app.models import Ticket


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_legacy_ts(dt: datetime | None) -> str | None:
    """Serialize a stored timestamptz the way legacy did: naive local ISO string.

    Legacy wrote datetime.now().isoformat() in the server's local tz (ADR-004).
    LEGACY_TZ is a placeholder until the real tz is confirmed.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:  # defensive; storage is timestamptz
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(settings.legacy_tz)).replace(tzinfo=None).isoformat()


def ticket_to_dict(t: Ticket) -> dict:
    """Full-row shape, matching legacy `SELECT *` serialization — assignee_id included
    even though app code never sets it (Q2)."""
    return {
        "id": t.id,
        "title": t.title,
        "slug": t.slug,
        "priority": t.priority,
        "status": t.status,
        "assignee_id": t.assignee_id,
        "created_at": to_legacy_ts(t.created_at),
        "closed_at": to_legacy_ts(t.closed_at),
    }


async def lenient_json(request: Request) -> dict:
    """Q5: legacy used get_json(silent=True) or {} — malformed/absent JSON is {}."""
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}
