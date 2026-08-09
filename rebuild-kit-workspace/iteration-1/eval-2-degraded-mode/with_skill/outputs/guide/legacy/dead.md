# dead code

`ticketd/app/legacy_import.py` — a 2019 one-off spreadsheet importer. Zero inbound imports,
zero route references, and its own docstring says "Nothing imports this module." This is
DNP-001: conclusively dead on static evidence alone (module-level dead-ness needs no traffic
data, unlike route-level — contrast OQ-001). It is not ported, not tested, not mourned.

Honorable mentions of inert cruft (DNP-005): an unused `import smtplib` in server.py and the
contractor's trailing `# tweak 1/2/3` scratch comments.
