#!/usr/bin/env python3
"""State-dump helper (legacy side): print the DB as canonical JSON, or column checksums.

  dump_sqlite.py --db path.sqlite3                 -> {"tickets":[...], "reset_tokens":[...]}
  dump_sqlite.py --db path.sqlite3 --checksum      -> md5 checksums matching reconciliation.sql R3/R10

The modern side must provide dump_postgres.py printing the SAME JSON shape (tables ->
list of row objects ordered by rowid/id, column names as in its schema). Contract:
verification/harness/README.md.
"""
import argparse
import hashlib
import json
import sqlite3

TABLES = ["tickets", "users", "reset_tokens"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--checksum", action="store_true")
    ap.add_argument("--tables", default=",".join(TABLES))
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    if args.checksum:
        rows = con.execute(
            "SELECT title||'|'||slug||'|'||coalesce(priority,'')||'|'||status AS l "
            "FROM tickets ORDER BY id").fetchall()
        t = hashlib.md5("\n".join(r["l"] for r in rows).encode()).hexdigest()
        rows = con.execute("SELECT email||'|'||name AS l FROM users ORDER BY id").fetchall()
        u = hashlib.md5("\n".join(r["l"] for r in rows).encode()).hexdigest()
        print(json.dumps({"tickets_checksum": t, "users_checksum": u}))
        return
    out = {}
    for tbl in args.tables.split(","):
        order = "ORDER BY id" if tbl != "reset_tokens" else "ORDER BY rowid"
        out[tbl] = [dict(r) for r in con.execute(f"SELECT * FROM {tbl} {order}").fetchall()]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
