import re

_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Exact port of legacy app/util.py: lowercase, collapse any run of non-alphanumeric
    characters to a single hyphen, strip leading/trailing hyphens, truncate to 64 characters.
    A title made entirely of stripped characters (e.g. "!!!") yields an empty string -- FIXED,
    reproduced as-is (see docs/features/draft/tickets-create.md P9 audit finding); slug
    uniqueness is WO-005/PB-003 scope, not this function's job."""
    s = _NON_ALNUM_RUN.sub("-", title.lower()).strip("-")
    return s[:64]
