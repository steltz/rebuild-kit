#!/usr/bin/env python3
"""Boots the legacy ticketd Flask app for real, without modifying legacy/ at all.

Two problems stand between "legacy/ exists" and "legacy/ actually runs":

1. `DB_PATH = "db/ticketd.sqlite3"` in app/server.py is a relative path resolved against the
   process's cwd at connect-time -- and legacy/db/ is read-only (the P0 guard strips write bits
   on the whole legacy tree). We solve this by chdir()-ing to a scratch run directory that has
   its own writable db/ subdir, then adding the legacy app root to sys.path so `import
   app.server` still resolves the actual legacy code. No file under legacy/ is touched.

2. `app/notify.py` opens a real SMTP connection to `smtp.internal:25`, which does not exist in
   any environment this harness runs in. We monkeypatch the *imported module object's*
   `send_mail` attribute at runtime (an in-memory rebinding in OUR process, not an edit to the
   file on disk) so the call records {to, body, ts} to a JSONL log instead of touching a
   socket. This is a documented, disclosed substitution for verification/replay/T1 purposes --
   the business logic that DECIDES to call send_mail (rate limiting, token generation, the
   `if changed:` guard) is 100% real legacy code, executed for real. Only the actual network
   syscall is stubbed. See docs/problem-brief.md and verification/harness/README.md.

Usage:
  legacy_wrapper.py --legacy-root <path to ticketd/> --run-dir <scratch dir>
                     --mail-log <path> --port 5001 [--seed <sql file>]
"""
import argparse
import os
import sqlite3
import sys
import time
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--mail-log", required=True)
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--seed", help="SQL file to initialize db/ticketd.sqlite3 from")
    args = ap.parse_args()

    legacy_root = Path(args.legacy_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    mail_log_path = Path(args.mail_log).resolve()  # resolve BEFORE chdir, it's used post-chdir
    (run_dir / "db").mkdir(parents=True, exist_ok=True)

    db_path = run_dir / "db" / "ticketd.sqlite3"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    if args.seed:
        conn.executescript(Path(args.seed).read_text())
    else:
        conn.executescript((legacy_root / "db" / "schema.sql").read_text())
    conn.commit()
    conn.close()

    sys.path.insert(0, str(legacy_root))
    os.chdir(run_dir)  # DB_PATH="db/ticketd.sqlite3" now resolves under run_dir/db/

    import app.notify as notify_mod

    def fake_send_mail(to, body):
        with open(mail_log_path, "a") as f:
            f.write(json.dumps({"to": to, "body": body, "ts": time.time()}) + "\n")

    notify_mod.send_mail = fake_send_mail  # patch before app.server imports it by name

    import app.server as server_mod

    server_mod.send_mail = fake_send_mail  # belt-and-suspenders: patch the imported name too

    print(f"[legacy_wrapper] booted from {legacy_root}, cwd={run_dir}, db={db_path}, "
          f"mail stubbed -> {mail_log_path}", file=sys.stderr)
    server_mod.app.run(port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
