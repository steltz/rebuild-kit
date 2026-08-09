# *(dead)* (how it works today)

`ticketd/app/legacy_import.py` — a one-off importer from the 2019 spreadsheet era, seven lines,
one function. Its own docstring says "nothing imports this module," and that checks out: no route
registers it, nothing else in the tree references it. Zero ambiguity here, unlike the export
route — this one isn't carried forward, full stop (PB-009, `docs/do-not-port.md`).
