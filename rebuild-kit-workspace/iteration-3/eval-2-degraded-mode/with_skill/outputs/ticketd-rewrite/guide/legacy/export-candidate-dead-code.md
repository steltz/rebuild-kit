# Export (candidate dead code) (how it works today)

`GET /internal/export/csv` dumps every ticket as unquoted, unescaped CSV. The route's own
comment says it was "written for the 2020 audit; no caller since" — plausible testimony, but
unconfirmed (no access logs exist to verify it). Worth knowing even if it's dead: the CSV
building is a real bug by inspection (`f"{r['id']},{r['title']},{r['status']}"` — a title
containing a comma corrupts the row; a title starting with `=`/`+`/`-`/`@` is a classic
spreadsheet formula-injection vector if the export is ever opened in Excel/Sheets).
