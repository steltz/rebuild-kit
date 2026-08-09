"""
Ported verbatim from ticketd/app/util.py:slugify.

Collision behavior (two different titles can produce the same slug) is
preserved on purpose — see docs/01-LEGACY-BEHAVIOR-INVENTORY.md. We have no
evidence on how often this happens in production or whether anything
depends on slug uniqueness, so we didn't add a uniqueness constraint or
disambiguation suffix here. Revisit once evidence exists.
"""
import re


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
