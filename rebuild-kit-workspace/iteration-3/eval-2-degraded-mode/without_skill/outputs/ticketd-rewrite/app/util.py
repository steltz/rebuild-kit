import re


def slugify(text: str) -> str:
    """Matches legacy app/util.py exactly, including the known collision
    behavior (e.g. "Fix DB" and "fix db!" both slugify to "fix-db") — not
    deduplicated here, see docs/OPEN_QUESTIONS.md #3."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
