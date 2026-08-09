#!/usr/bin/env python3
"""Twin-boot launcher for legacy/ (T2/T3 replay only — never used to serve real traffic).

Boots the UNMODIFIED legacy Flask app (imported via PYTHONPATH, source untouched) against a
freshly-seeded SQLite DB in a scratch working directory OUTSIDE legacy/ (legacy/app/server.py
hardcodes a relative DB path "db/ticketd.sqlite3"; running with cwd=<scratch> instead of
cwd=<legacy> keeps every byte under legacy/ read-only while still using the real app code).

Usage: run_legacy_server.py --legacy-root <path> --scratch <path> --port 5001 [--seed <sql file>]
"""
import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--legacy-root", required=True)
ap.add_argument("--scratch", required=True)
ap.add_argument("--port", type=int, default=5001)
ap.add_argument("--seed", required=True, help="SQL file to initialize the scratch DB")
args = ap.parse_args()

legacy_root = Path(args.legacy_root).resolve()
scratch = Path(args.scratch).resolve()
if scratch.exists():
    shutil.rmtree(scratch)
(scratch / "db").mkdir(parents=True)

db_path = scratch / "db" / "ticketd.sqlite3"
conn = sqlite3.connect(str(db_path))
conn.executescript(Path(args.seed).read_text())
conn.commit()
conn.close()

sys.path.insert(0, str(legacy_root))
sys.path.insert(0, str(Path(__file__).parent))
import smtp_stub
smtp_stub.install()

import os
os.chdir(scratch)
os.environ["TICKETD_SMTP_LOG"] = str(scratch / "sent_mail.jsonl")

from app.server import app  # noqa: E402  (legacy source, unmodified, imported via PYTHONPATH)

app.run(port=args.port)
