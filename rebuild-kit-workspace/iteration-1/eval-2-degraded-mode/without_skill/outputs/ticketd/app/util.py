import re


def slugify(text):
    # collisions possible: two tickets named "Fix DB" and "fix db!" share a slug
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
# note
