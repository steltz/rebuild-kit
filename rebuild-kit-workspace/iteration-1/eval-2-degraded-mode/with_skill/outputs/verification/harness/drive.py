#!/usr/bin/env python3
"""Drive a T2 input set against one booted side and record normalized traces (JSONL,
replay.py shape). Stdlib only.

Usage:
  drive.py --base-url http://127.0.0.1:5001 --input-set ../replay/input-sets/core.jsonl \
           --emails-from file:/path/to/smtp-log.jsonl --db /path/to/ticketd.sqlite3 \
           --out traces.jsonl
  (modern side: --emails-from url:http://.../__harness__/emails
                --state-url http://.../__harness__/state)

Capture rules (part of the harness contract — see README.md):
  - Response: status + parsed JSON body (raw text for non-JSON). 5xx bodies are recorded as
    null: framework error pages are not part of the frozen contract.
  - No response headers are captured; header-level assertions live in characterization tests.
  - Emails: after each request, newly observed dispatches are classified
    (ticket_closed | reset_token) and recorded as state.email_dispatch
    {kind, to, mode, ref}. mode is 'sync' for file: sources (in-request SMTP capture),
    'queued' for url: sources (modern dispatch seam).
  - Tokens: every presentable reset token observed in an email is globally replaced by a
    stable placeholder <TOKEN:trace-id> in everything written — both sides converge on
    identical placeholders. Input steps may reference "$TOKEN[trace-id]" to use a captured
    token in a later request.
  - A step with "capture_state": true dumps the DB (ordered, stable keys) into
    state.db_dump and derives state.reset_token_storage
    (md5-plaintext | hashed | empty) for ED-003.
"""
import argparse
import json
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

TOKEN_MAIL_RE = re.compile(r"reset token:\s*(\S+)")
HEX32_RE = re.compile(r"^[0-9a-f]{32}$")


def http(base, req):
    url = base + req["path"]
    data = None
    headers = dict(req.get("headers") or {})
    if "json" in req:
        data = json.dumps(req["json"]).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers,
                               method=req.get("method", "GET"))
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        status, raw = resp.status, resp.read()
        ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
    if status >= 500:
        return status, None
    if "application/json" in ctype:
        return status, json.loads(raw.decode())
    return status, raw.decode("utf-8", "replace")


def read_emails(src, seen):
    """Return (new_events, mode). src = 'file:PATH' | 'url:URL'."""
    kind, _, loc = src.partition(":")
    if kind == "file":
        lines = Path(loc).read_text().splitlines() if Path(loc).exists() else []
        events = [json.loads(l) for l in lines if l.strip()]
        mode = "sync"
    else:
        with urllib.request.urlopen(loc, timeout=10) as r:
            events = json.loads(r.read().decode())
        mode = "queued"
    new = events[seen:]
    return new, mode, len(events)


def classify(ev, mode):
    data = ev.get("data", "")
    to = (ev.get("to") or [None])[0] if isinstance(ev.get("to"), list) else ev.get("to")
    m = TOKEN_MAIL_RE.search(data)
    if m:
        return {"kind": "reset_token", "to": to, "mode": mode, "ref": m.group(1)}, m.group(1)
    if data.startswith("closed: ") or "closed: " in data:
        title = data.split("closed: ", 1)[1].splitlines()[0]
        return {"kind": "ticket_closed", "to": to, "mode": mode, "ref": title}, None
    return {"kind": "other", "to": to, "mode": mode, "ref": data[:80]}, None


def dump_db(db_path=None, state_url=None):
    if state_url:
        with urllib.request.urlopen(state_url, timeout=10) as r:
            return json.loads(r.read().decode())
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = {}
    for tbl in ("tickets", "users", "reset_tokens"):
        rows = conn.execute(f"SELECT * FROM {tbl} ORDER BY rowid").fetchall()
        out[tbl] = [dict(r) for r in rows]
    conn.close()
    return out


def storage_mode(reset_rows):
    if not reset_rows:
        return "empty"
    if all("token_hash" in r for r in reset_rows):
        return "hashed"
    if all(HEX32_RE.match(str(r.get("token", ""))) for r in reset_rows):
        return "md5-plaintext"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--input-set", required=True)
    ap.add_argument("--emails-from", required=True)
    ap.add_argument("--db")
    ap.add_argument("--state-url")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    steps = [json.loads(l) for l in Path(args.input_set).read_text().splitlines()
             if l.strip() and not l.strip().startswith("#")]
    tokens = {}          # raw token -> placeholder
    token_by_trace = {}  # trace id -> raw token
    seen_emails = 0
    traces = []

    for step in steps:
        tid = step["id"]
        state = {}
        if step.get("capture_state"):
            db = dump_db(args.db, args.state_url)
            state["reset_token_storage"] = storage_mode(db.get("reset_tokens", []))
            state["db_dump"] = db
            traces.append({"id": tid, "request": None,
                           "response": None, "state": state})
            continue
        req = json.loads(json.dumps(step["request"]))  # deep copy
        # resolve $TOKEN[trace-id] templates
        def resolve(o):
            if isinstance(o, str):
                m = re.fullmatch(r"\$TOKEN\[(.+)\]", o)
                if m:
                    return token_by_trace[m.group(1)]
                return o
            if isinstance(o, dict):
                return {k: resolve(v) for k, v in o.items()}
            if isinstance(o, list):
                return [resolve(v) for v in o]
            return o
        req = resolve(req)
        status, body = http(args.base_url, req)
        new, mode, seen_emails = read_emails(args.emails_from, seen_emails)
        dispatch = None
        for ev in new:
            d, raw_token = classify(ev, mode)
            if raw_token:
                tokens.setdefault(raw_token, f"<TOKEN:{tid}>")
                token_by_trace.setdefault(tid, raw_token)
                d["ref"] = tokens[raw_token]
            dispatch = d if dispatch is None else dispatch
        state["email_dispatch"] = dispatch
        traces.append({"id": tid, "request": req,
                       "response": {"status": status, "body": body}, "state": state})

    text = "\n".join(json.dumps(t, sort_keys=True) for t in traces) + "\n"
    for raw, ph in tokens.items():
        text = text.replace(raw, ph)
    Path(args.out).write_text(text)
    print(f"{len(traces)} traces → {args.out}")


if __name__ == "__main__":
    main()
