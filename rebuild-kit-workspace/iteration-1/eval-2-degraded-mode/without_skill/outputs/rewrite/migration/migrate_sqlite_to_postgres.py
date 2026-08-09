#!/usr/bin/env python3
"""One-shot SQLite -> Postgres migration for ticketd.

Usage:
    python migrate_sqlite_to_postgres.py \
        --sqlite /path/to/ticketd.sqlite3 \
        --pg postgresql://localhost/ticketd \
        --legacy-tz Europe/Berlin          # REQUIRED, see data-migration-plan.md

Requires: pip install psycopg[binary]   (sqlite3 is stdlib)

Behavior:
- Preserves legacy ids (OVERRIDING SYSTEM VALUE), then resets identity sequences.
- Naive legacy timestamps are interpreted in --legacy-tz and stored as UTC.
- Unmappable rows -> migration_quarantine.jsonl; non-empty quarantine fails the run
  unless --allow-quarantine.
- reset_tokens are skipped by default (plaintext short-lived legacy tokens; ADR-002).
- Aborts if target tables are not empty.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    import psycopg
except ImportError:
    sys.exit("pip install 'psycopg[binary]' first")

QUARANTINE_FILE = "migration_quarantine.jsonl"


def parse_legacy_ts(value, tz: ZoneInfo):
    """Legacy wrote datetime.now().isoformat() — naive local ISO. Tolerate None."""
    if value in (None, ""):
        return None
    dt = datetime.fromisoformat(str(value))  # raises on drifted formats -> quarantine
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", required=True)
    ap.add_argument("--pg", required=True)
    ap.add_argument("--legacy-tz", required=True,
                    help="IANA tz the legacy server wrote naive timestamps in. "
                         "UNKNOWN as of 2026-08-08 — confirm with ops before running.")
    ap.add_argument("--skip-reset-tokens", action="store_true", default=True)
    ap.add_argument("--migrate-reset-tokens", dest="skip_reset_tokens",
                    action="store_false",
                    help="Copy legacy reset tokens (hashes of the legacy md5 values). "
                         "Rarely wanted; default is to drop them.")
    ap.add_argument("--allow-quarantine", action="store_true")
    args = ap.parse_args()

    tz = ZoneInfo(args.legacy_tz)
    src = sqlite3.connect(args.sqlite)
    src.row_factory = sqlite3.Row
    quarantine = []

    with psycopg.connect(args.pg) as pg:
        with pg.cursor() as cur:
            for table in ("users", "tickets", "reset_tokens", "outbox_emails"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                if cur.fetchone()[0]:
                    sys.exit(f"target table {table} is not empty; aborting")

            # --- users (Q2: may be empty; may be written by an unknown external system)
            n_users = 0
            for r in src.execute("SELECT * FROM users"):
                cur.execute(
                    "INSERT INTO users (id, email, name) OVERRIDING SYSTEM VALUE "
                    "VALUES (%s, %s, %s)", (r["id"], r["email"], r["name"]))
                n_users += 1

            # --- tickets (per-row savepoints: constraint failures -> quarantine,
            #     not a dead transaction; expected sources per intake C2/C4/C6)
            n_tickets = 0
            for r in src.execute("SELECT * FROM tickets"):
                cur.execute("SAVEPOINT row_sp")
                try:
                    cur.execute(
                        "INSERT INTO tickets (id, title, slug, priority, status, "
                        " assignee_id, created_at, closed_at) OVERRIDING SYSTEM VALUE "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (r["id"], r["title"], r["slug"], r["priority"], r["status"],
                         r["assignee_id"],
                         parse_legacy_ts(r["created_at"], tz),
                         parse_legacy_ts(r["closed_at"], tz)))
                    cur.execute("RELEASE SAVEPOINT row_sp")
                    n_tickets += 1
                except Exception as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                    quarantine.append({"table": "tickets", "row": dict(r),
                                       "reason": repr(exc)})

            # --- reset tokens
            n_tokens = 0
            if not args.skip_reset_tokens:
                import hashlib
                for r in src.execute("SELECT * FROM reset_tokens"):
                    cur.execute(
                        "INSERT INTO reset_tokens (email, token_hash, created_at) "
                        "VALUES (%s, %s, %s)",
                        (r["email"],
                         hashlib.sha256(str(r["token"]).encode()).hexdigest(),
                         datetime.fromtimestamp(r["created_ts"], tz=timezone.utc)))
                    n_tokens += 1

            for table in ("users", "tickets"):
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))")

        if quarantine:
            with open(QUARANTINE_FILE, "w") as f:
                for row in quarantine:
                    f.write(json.dumps(row, default=str) + "\n")
            if not args.allow_quarantine:
                sys.exit(f"{len(quarantine)} rows quarantined -> {QUARANTINE_FILE}; "
                         "rerun with --allow-quarantine to commit without them")
        pg.commit()

    print(f"migrated: {n_users} users, {n_tickets} tickets, {n_tokens} reset tokens; "
          f"quarantined: {len(quarantine)}")


if __name__ == "__main__":
    main()
