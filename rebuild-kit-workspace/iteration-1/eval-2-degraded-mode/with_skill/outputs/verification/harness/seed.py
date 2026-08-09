#!/usr/bin/env python3
"""Seed a fresh legacy SQLite DB for a harness run.

Creates <rundir>/db/ticketd.sqlite3 from docs/contracts/ddl.sql plus the shared seed data
in seed.json. Seed tokens get relative ages (age_s) so time-window behaviors (30-min expiry)
are exercisable without time travel. The modern side must load the SAME seed.json through
its own loader such that seeded presentable tokens are confirmable under its storage scheme
(see README.md — harness contract).
"""
import argparse
import json
import sqlite3
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True)
    args = ap.parse_args()
    rundir = Path(args.rundir)
    (rundir / "db").mkdir(parents=True, exist_ok=True)
    db_path = rundir / "db" / "ticketd.sqlite3"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    ddl = (ROOT / "docs" / "contracts" / "ddl.sql").read_text()
    ddl = "\n".join(l for l in ddl.splitlines() if not l.startswith("--"))
    conn.executescript(ddl)
    seed = json.loads((HERE / "seed.json").read_text())
    for u in seed.get("users", []):
        conn.execute("INSERT INTO users (id, email, name) VALUES (?, ?, ?)",
                     (u["id"], u["email"], u["name"]))
    now = time.time()
    for t in seed.get("reset_tokens", []):
        conn.execute("INSERT INTO reset_tokens (email, token, created_ts) VALUES (?, ?, ?)",
                     (t["email"], t["token"], now - t["age_s"]))
    conn.commit()
    conn.close()
    print(f"seeded {db_path}")


if __name__ == "__main__":
    main()
