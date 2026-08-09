#!/usr/bin/env python3
"""Drives a scripted (T2) session against a running legacy/modern instance and records JSONL
traces in the format replay.py expects: {"id","request","response","state"}.

Stdlib only (matches replay.py's own dependency policy) — urllib instead of requests.

Usage: capture_traces.py --base-url http://127.0.0.1:5055 --db <sqlite path> \
           --script verification/replay/scripts/tickets.json \
           --out verification/replay/traces/tickets-legacy.jsonl
"""
import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path


def do_request(base_url, step):
    url = base_url + step["path"]
    data = None
    headers = dict(step.get("headers", {}))
    if "json_body" in step:
        data = json.dumps(step["json_body"]).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=step["method"])
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            body_bytes = resp.read()
            status = resp.status
            resp_headers = dict(resp.getheaders())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        status = e.code
        resp_headers = dict(e.headers or {})
    try:
        body = json.loads(body_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = body_bytes.decode(errors="replace")
    return status, resp_headers, body


def dump_state(db_path, tables):
    if not db_path or not Path(db_path).exists():
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    dump = {}
    for t in tables:
        dump[t] = [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()]
    conn.close()
    return {"db_dump": dump}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--db", help="sqlite path for post-request state capture")
    ap.add_argument("--state-tables", default="tickets,reset_tokens")
    ap.add_argument("--script", required=True, help="JSON file: list of step dicts")
    ap.add_argument("--out", required=True)
    ap.add_argument("--vars-out", help="write captured response fields for later steps (e.g. created id)")
    args = ap.parse_args()

    steps = json.loads(Path(args.script).read_text())
    tables = args.state_tables.split(",")
    ctx = {}  # simple template substitution context, e.g. {{last_id}}

    out_lines = []
    for step in steps:
        raw = json.dumps(step)
        for k, v in ctx.items():
            raw = raw.replace("{{" + k + "}}", str(v))
        step = json.loads(raw)

        status, headers, body = do_request(args.base_url, step)
        time.sleep(0.05)  # let SQLite commit / stub-write settle
        state = dump_state(args.db, tables) if args.db else None

        trace = {
            "id": step["id"],
            "request": {"method": step["method"], "path": step["path"],
                        "headers": step.get("headers", {}), "body": step.get("json_body")},
            "response": {"status": status, "headers": headers, "body": body},
            "state": state,
        }
        out_lines.append(json.dumps(trace))

        # capture vars for templating in later steps
        if isinstance(body, dict):
            for capture_name, field in step.get("capture", {}).items():
                cur = body
                for part in field.split("."):
                    cur = cur.get(part) if isinstance(cur, dict) else None
                ctx[capture_name] = cur

        # capture vars from post-request DB state, e.g. "reset_tokens.-1.token" = last row's token
        if state:
            for capture_name, field in step.get("capture_state", {}).items():
                table, idx, col = field.split(".")
                rows = state["db_dump"].get(table, [])
                cur = rows[int(idx)].get(col) if rows else None
                ctx[capture_name] = cur

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out_lines) + "\n")
    print(f"{len(out_lines)} traces -> {args.out}")


if __name__ == "__main__":
    main()
