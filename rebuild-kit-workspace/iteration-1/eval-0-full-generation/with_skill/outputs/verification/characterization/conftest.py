"""Characterization suite (L2). Runs against EITHER tree:

  legacy (default):  boots via harness run-legacy.sh on :5093
  modern:            CHAR_TARGET=modern (boots via run-modern.sh on :5094), or point
                     CHAR_BASE_URL at an already-running instance and set CHAR_OUTBOX,
                     CHAR_AGE_CMD, CHAR_MAIL_MODE=queued.

Env contract:
  CHAR_BASE_URL   http://127.0.0.1:5093        (skips boot when preset)
  CHAR_OUTBOX     path to the mail sink JSONL
  CHAR_AGE_CMD    shell template with {email} {seconds} placeholders
  CHAR_MAIL_MODE  sync | queued  (queued polls the sink up to 3s)
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent.parent / "harness"


def _boot():
    target = os.environ.get("CHAR_TARGET", "legacy")
    if target == "legacy":
        port = "5093"
        subprocess.run([str(HARNESS / "run-legacy.sh"), port], check=True)
        run = HARNESS / "var" / "legacy-run"
        os.environ.setdefault("CHAR_OUTBOX", str(run / "outbox.jsonl"))
        os.environ.setdefault(
            "CHAR_AGE_CMD",
            f"python3 {HARNESS}/age_token_sqlite.py --db {run}/db/ticketd.sqlite3 "
            "--email {email} --seconds {seconds}")
        os.environ.setdefault("CHAR_MAIL_MODE", "sync")
    else:
        port = "5094"
        subprocess.run([str(HARNESS / "run-modern.sh"), port], check=True)
        run = HARNESS / "var" / "modern-run"
        os.environ.setdefault("CHAR_OUTBOX", str(run / "outbox.jsonl"))
        os.environ.setdefault("CHAR_AGE_CMD",
                              "%s/harness-age-token.sh {email} {seconds}"
                              % (HARNESS.parent.parent / "modern"))
        os.environ.setdefault("CHAR_MAIL_MODE", "queued")
    os.environ["CHAR_BASE_URL"] = f"http://127.0.0.1:{port}"
    return run / "server.pid"


@pytest.fixture(scope="session")
def api():
    pid_file = None
    if "CHAR_BASE_URL" not in os.environ:
        pid_file = _boot()
    yield Api(os.environ["CHAR_BASE_URL"])
    if pid_file and pid_file.exists():
        subprocess.run(["kill", pid_file.read_text().strip()], check=False)


class Api:
    def __init__(self, base):
        self.base = base
        self.outbox_path = os.environ.get("CHAR_OUTBOX")
        self.mail_mode = os.environ.get("CHAR_MAIL_MODE", "sync")

    def call(self, method, path, body=None, headers=None, raw=None):
        h = dict(headers or {})
        data = None
        if raw is not None:
            data, _ = raw.encode(), h.setdefault("Content-Type", "application/json")
        elif body is not None:
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=30)
            status, payload = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, payload = e.code, e.read()
        try:
            return status, json.loads(payload)
        except ValueError:
            return status, payload.decode(errors="replace")

    def outbox(self):
        try:
            return [json.loads(l) for l in open(self.outbox_path) if l.strip()]
        except FileNotFoundError:
            return []

    def wait_mail(self, count_from, timeout=3.0):
        """Return messages beyond index count_from, polling in queued mode."""
        deadline = time.time() + (timeout if self.mail_mode == "queued" else 0.2)
        while True:
            msgs = self.outbox()[count_from:]
            if msgs or time.time() > deadline:
                return msgs
            time.sleep(0.1)

    def age_tokens(self, email, seconds):
        cmd = os.environ["CHAR_AGE_CMD"].format(email=email, seconds=seconds)
        subprocess.run(cmd, shell=True, check=True)


@pytest.fixture()
def unique_email():
    return f"char-{uuid.uuid4().hex[:10]}@corp.example.com"
