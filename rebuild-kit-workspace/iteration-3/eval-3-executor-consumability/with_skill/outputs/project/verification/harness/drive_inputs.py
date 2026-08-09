#!/usr/bin/env python3
"""T2 input driver: sends a scripted HTTP session to a running ticketd instance (legacy or
modern, either boots the same way per run-legacy.sh / run-modern.sh) and records each step as
a trace line in the exact JSONL shape verification/replay/../scripts/replay.py expects:
  {"id": ..., "request": {...}, "response": {"status", "headers", "body"}, "state": {"db_dump": {...}}}

Input set format (verification/replay/inputs/*.jsonl), one JSON object per line:
  {
    "id": "auth-reset-confirm-002-expired",
    "pre_sql": ["INSERT INTO reset_tokens (...) VALUES (..., {now} - 1800 - 60)"],
        # optional; {now} is substituted with the current epoch float BEFORE exec. Runs
        # directly against the run's sqlite file -- used to seed states hard to reach purely
        # through the HTTP surface (e.g. an already-expired token) without waiting for real time.
    "request": {"method": "POST", "path": "/api/auth/reset/confirm",
                "headers": {}, "body": {"token": "{{vars.last_mail_token}}"}}
        # {{vars.NAME}} substituted from values captured by a prior step's "capture_mail_token".
    "capture_mail_token": "last_mail_token"   # optional: after this request, parse the newest
        # line appended to the mail log and store the "reset token: X" value under this name.
  }

Usage:
  drive_inputs.py --base-url http://127.0.0.1:5001 --db <sqlite path> --mail-log <path>
                   --input <inputs.jsonl> --out <traces.jsonl>
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse

TABLES = ["tickets", "users", "reset_tokens"]


def _is_postgres_dsn(db):
    return db.startswith("postgresql://") or db.startswith("postgresql+psycopg://")


def _dump_db_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = {}
    for t in TABLES:
        try:
            rows = conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
            out[t] = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            out[t] = None
    conn.close()
    return out


def _dump_db_postgres(dsn):
    """modern/ (WO-001+) runs on Postgres, not sqlite -- run-modern.sh prints a
    postgresql[+psycopg]:// DSN (see its header comment) instead of run-legacy.sh's sqlite
    file path. Shells out to `psql` (already a harness dependency once Postgres is involved;
    see README.md) rather than adding a Python driver dependency to this stdlib-only script.
    `ctid` (physical row location) stands in for sqlite's `rowid` as an insertion-order proxy
    -- true for an insert-only, unvacuumed seed+replay run, which is all this harness ever
    does to these tables."""
    u = urlparse(dsn.replace("postgresql+psycopg://", "postgresql://", 1))
    conn_args = ["-h", u.hostname or "127.0.0.1", "-p", str(u.port or 5432)]
    if u.username:
        conn_args += ["-U", u.username]
    conn_args += ["-d", (u.path or "/").lstrip("/")]

    out = {}
    for t in TABLES:
        query = f"SELECT COALESCE(json_agg(t ORDER BY t.ctid), '[]'::json) FROM {t} t;"
        try:
            result = subprocess.run(
                ["psql", *conn_args, "-tAc", query],
                capture_output=True, text=True, check=True,
            )
            out[t] = json.loads(result.stdout.strip())
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            out[t] = None
    return out


def dump_db(db_path):
    if _is_postgres_dsn(db_path):
        return _dump_db_postgres(db_path)
    return _dump_db_sqlite(db_path)


def substitute(obj, variables):
    if isinstance(obj, str):
        m = re.fullmatch(r"\{\{vars\.(\w+)\}\}", obj)
        if m:
            return variables.get(m.group(1))
        return obj
    if isinstance(obj, dict):
        return {k: substitute(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, variables) for v in obj]
    return obj


def send(base_url, req):
    url = base_url.rstrip("/") + req["path"]
    method = req.get("method", "GET")
    body = req.get("body")
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(req.get("headers") or {})
    if data is not None:
        headers.setdefault("Content-Type", "application/json")
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            status = resp.status
            raw = resp.read()
            resp_headers = resp.headers
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        resp_headers = e.headers
    # resp_headers is an email.message.Message (via http.client.HTTPMessage) -- .get() is
    # case-insensitive by design, unlike a plain dict built from .items(). This matters once a
    # server other than Werkzeug's dev server is in the mix: uvicorn emits "content-type"
    # (lowercase), and a case-sensitive dict lookup against "Content-Type" silently misses it,
    # which then skips JSON body parsing entirely -- discovered running this for real against
    # modern/, exactly the kind of gap P7 execution catches that static reading wouldn't.
    ctype = (resp_headers.get("Content-Type", "") if resp_headers else "")
    if "application/json" in ctype:
        try:
            parsed = json.loads(raw.decode()) if raw else {}
        except json.JSONDecodeError:
            parsed = raw.decode(errors="replace")
    else:
        parsed = raw.decode(errors="replace")
    return status, {"Content-Type": ctype}, parsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--db", required=True,
                     help="running instance's sqlite file path, or a postgresql[+psycopg]:// DSN")
    ap.add_argument("--mail-log", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    variables = {}
    out_lines = []
    mail_log = Path(args.mail_log)

    with open(args.input) as f:
        entries = [json.loads(l) for l in f if l.strip()]

    for entry in entries:
        if entry.get("pre_sql"):
            if _is_postgres_dsn(args.db):
                # No WO through WO-001 exercises pre_sql against modern/ (none of its suites'
                # inputs use it) -- fail loudly rather than silently no-op-ing or mis-seeding
                # state if a future WO's suite (e.g. auth-reset-confirm) hits this path before
                # someone adds a psql-based pre_sql executor to match _dump_db_postgres above.
                raise NotImplementedError(
                    "pre_sql against a postgres DSN is not yet implemented in drive_inputs.py "
                    "-- see the comment here and _dump_db_postgres()."
                )
            conn = sqlite3.connect(args.db)
            now = time.time()
            for stmt in entry["pre_sql"]:
                conn.execute(stmt.replace("{now}", repr(now)))
            conn.commit()
            conn.close()

        req = substitute(entry["request"], variables)
        mail_lines_before = mail_log.read_text().splitlines() if mail_log.exists() else []
        status, headers, body = send(args.base_url, req)
        mail_lines_after = mail_log.read_text().splitlines() if mail_log.exists() else []

        if entry.get("capture_mail_token") and len(mail_lines_after) > len(mail_lines_before):
            newest = json.loads(mail_lines_after[-1])
            m = re.search(r"reset token: (\S+)", newest.get("body", ""))
            if m:
                variables[entry["capture_mail_token"]] = m.group(1)

        trace = {
            "id": entry["id"],
            "request": req,
            "response": {"status": status, "headers": headers, "body": body},
            "state": {"db_dump": dump_db(args.db)},
        }
        out_lines.append(json.dumps(trace))
        print(f"  {entry['id']}: {req.get('method','GET')} {req['path']} -> {status}",
              file=sys.stderr)

    Path(args.out).write_text("\n".join(out_lines) + "\n")
    print(f"[drive_inputs] {len(out_lines)} traces -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
