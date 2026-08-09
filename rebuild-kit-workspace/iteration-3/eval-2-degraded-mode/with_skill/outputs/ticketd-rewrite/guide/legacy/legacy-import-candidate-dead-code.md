# Legacy import (candidate dead code) (how it works today)

`legacy/app/legacy_import.py` is seven lines — a CSV-to-dict importer for "the 2019 spreadsheet
era," by its own docstring's account. It isn't a route; nothing in the legacy tree imports it
(confirmed structurally: zero inbound dependency edges in `inventory.json`). There is no
narrative here beyond that — it's dead weight, most likely, pending the same `OQ-003` ruling as
the CSV export route.
