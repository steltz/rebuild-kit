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
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

TABLES = ["tickets", "users", "reset_tokens"]


def dump_db(db_path):
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
            resp_headers = dict(resp.headers.items())
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        resp_headers = dict(e.headers.items()) if e.headers else {}
    ctype = resp_headers.get("Content-Type", "")
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
    ap.add_argument("--db", required=True, help="path to the running instance's sqlite file")
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
