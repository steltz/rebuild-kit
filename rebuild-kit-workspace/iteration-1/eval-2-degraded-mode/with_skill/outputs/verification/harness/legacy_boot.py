#!/usr/bin/env python3
"""Boot the pinned legacy app for harness runs — WITHOUT touching the legacy tree.

Instrumentation (harness-level, documented, not a legacy modification):
  1. smtplib.SMTP is patched to connect to the local capturing stub (SMTP_STUB_PORT)
     instead of the hardcoded, unreachable 'smtp.internal' (ticketd/app/notify.py:6).
     Send semantics stay synchronous-in-request — the PB-001 behavior is preserved.
  2. cwd is a scratch rundir so the relative DB_PATH 'db/ticketd.sqlite3'
     (ticketd/app/server.py:14) resolves OUTSIDE the read-only legacy tree.

Env: LEGACY_DIR (abs path to pinned tree), RUNDIR, PORT, SMTP_STUB_PORT.
"""
import os
import smtplib
import sys

stub_port = int(os.environ["SMTP_STUB_PORT"])
_orig_init = smtplib.SMTP.__init__


def _patched_init(self, host="", port=0, *a, **kw):
    kw.pop("timeout", None)
    _orig_init(self, "127.0.0.1", stub_port, timeout=10)


smtplib.SMTP.__init__ = _patched_init

os.chdir(os.environ["RUNDIR"])
sys.path.insert(0, os.environ["LEGACY_DIR"])

from app import server  # noqa: E402  (imports the pinned tree read-only)

server.app.run(port=int(os.environ["PORT"]))
