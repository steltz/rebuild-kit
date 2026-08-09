"""Port of ticketd/app/util.py — identical output, collisions and all (Q7)."""
import re


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
