"""Shared twin-boot driver library. Used by both run-legacy.sh (against legacy/, imported
read-only) and run-modern.sh (against modern/, once it exists). Boots the target app against a
fresh SQLite DB per trace, drives one JSON request through it, and records a normalized trace
line: {id, request, response, state}. Stdlib + Flask test client only (legacy's own framework);
a Postgres/FastAPI equivalent driver is the executor's job to add for modern/ (see
verification/harness/README.md) once WO-000-ish app scaffolding exists — this file's
`run_one_legacy` path is complete and is the reference for what that equivalent must produce.
"""
import json
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

DDL_TABLES = ["tickets", "users", "reset_tokens"]


def fresh_sqlite_db(db_path, ddl_path):
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(Path(ddl_path).read_text())
    conn.commit()
    conn.close()


def _resolve_seed_value(v):
    """Corpus timestamps must be relative to run time, not baked into the JSON file — a token
    seeded "1801 seconds ago" needs to still be 1801 seconds ago whenever the harness runs.
    {"relative_seconds": -1801} resolves to time.time() - 1801 at seed time."""
    if isinstance(v, dict) and "relative_seconds" in v:
        return time.time() + v["relative_seconds"]
    return v


def seed_db(db_path, seed_rows):
    if not seed_rows:
        return
    conn = sqlite3.connect(str(db_path))
    for row in seed_rows:
        table = row["table"]
        values = {k: _resolve_seed_value(v) for k, v in row["values"].items()}
        cols = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(values.values()))
    conn.commit()
    conn.close()


def dump_db(db_path, tables=DDL_TABLES):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    out = {}
    for t in tables:
        rows = conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
        out[t] = [dict(r) for r in rows]
    conn.close()
    return out


class RecordingSMTP:
    """Drop-in replacement for smtplib.SMTP used only inside the harness process — never
    touches legacy/ on disk, purely a runtime monkeypatch of the stdlib smtplib module for the
    duration of one request. Records dispatches instead of opening a real socket."""
    _log = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendmail(self, from_addr, to_addrs, body):
        RecordingSMTP._log.append({
            "mode": "sync",  # legacy always dispatches inline before responding; see PB-001
            "to": list(to_addrs) if isinstance(to_addrs, (list, tuple)) else [to_addrs],
            "kind": _classify_body(body),
        })


def _classify_body(body):
    # Coarse classification only — raw body/token text is intentionally NOT captured in the
    # trace (PB-002 changes the token's literal format; comparing it would be a false failure,
    # not a real one). See verification/replay/diff-rules.yaml header comment.
    if body.startswith("closed:"):
        return "ticket_closed"
    if body.startswith("reset token:"):
        return "reset_token_issued"
    return "unknown"


def _email_dispatch_field(email_log):
    """scripts/replay.py's field-path lookup (used by expected-divergences.yaml matching) only
    walks dict keys, not list indices — and every route in this app sends at most one email per
    request. So collapse to: None (no dispatch), the single dispatch dict (the common case, so
    ED entries can target "$.state.email_dispatch.mode" directly), or the raw list if more than
    one dispatch somehow occurred (defensive; not exercised by any current corpus entry)."""
    if not email_log:
        return None
    if len(email_log) == 1:
        return email_log[0]
    return list(email_log)


@contextmanager
def capture_email():
    RecordingSMTP._log = []
    with mock.patch("smtplib.SMTP", RecordingSMTP):
        yield RecordingSMTP._log


def _exec_flask_request(client, req):
    resp = client.open(
        req["path"],
        method=req["method"],
        headers=req.get("headers") or {},
        json=req.get("json") if req.get("json") is not None else None,
    )
    try:
        body = resp.get_json(silent=True)
        if body is None:
            body = resp.get_data(as_text=True)
    except Exception:
        body = resp.get_data(as_text=True)
    return {"status": resp.status_code, "headers": dict(resp.headers), "body": body}


def run_one_legacy(app, db_path, trace_spec, ddl_path):
    """trace_spec: {"id", "seed_rows": [...], "request": {...}} for a single request, OR
    {"id", "seed_rows": [...], "steps": [{"request": {...}}, ...]} to drive several requests
    against the SAME persisted DB in sequence (e.g. to prove single-use token deletion) — email
    dispatches accumulate across all steps; only the final state is dumped."""
    fresh_sqlite_db(db_path, ddl_path)
    seed_db(db_path, trace_spec.get("seed_rows"))
    client = app.test_client()
    with capture_email() as email_log:
        if "steps" in trace_spec:
            responses = [_exec_flask_request(client, step["request"]) for step in trace_spec["steps"]]
            state = {"db_dump": dump_db(db_path), "email_dispatch": _email_dispatch_field(email_log)}
            return {"id": trace_spec["id"],
                    "steps": [{"request": s["request"], "response": r}
                              for s, r in zip(trace_spec["steps"], responses)],
                    "state": state}
        req = trace_spec["request"]
        response = _exec_flask_request(client, req)
        state = {"db_dump": dump_db(db_path), "email_dispatch": _email_dispatch_field(email_log)}
        return {"id": trace_spec["id"], "request": req, "response": response, "state": state}


def load_corpus(path):
    out = []
    for line in Path(path).open():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def write_traces(path, traces):
    Path(path).write_text("\n".join(json.dumps(t, sort_keys=True) for t in traces) + "\n")


def fail(msg):
    print(f"HARNESS ERROR: {msg}", file=sys.stderr)
    sys.exit(1)
