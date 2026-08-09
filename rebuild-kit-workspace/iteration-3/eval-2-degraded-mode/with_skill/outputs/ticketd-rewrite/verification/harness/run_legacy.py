#!/usr/bin/env python3
"""Boot legacy/ against each corpus file under verification/replay/corpus/ and record the
LEGACY GOLDEN trace to verification/replay/traces/<feature>.legacy.jsonl. Per schema.md input
tiers: legacy golden outputs are recorded once per input set and cached — re-run this only when
the corpus changes or the legacy pin moves (scripts/staleness_check.py flags the latter).
Resolves legacy_dir through rebuild.json, per rebuild-kit design principle 6.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verification" / "harness" / "lib"))
import driver  # noqa: E402

REBUILD_JSON = json.loads((ROOT / "rebuild.json").read_text())
LEGACY_DIR = ROOT / REBUILD_JSON["layout"]["legacy_dir"]
DDL_PATH = ROOT / "docs" / "contracts" / "ddl.sql"
CORPUS_DIR = ROOT / "verification" / "replay" / "corpus"
TRACES_DIR = ROOT / "verification" / "replay" / "traces"


def load_legacy_app():
    sys.path.insert(0, str(LEGACY_DIR))
    from app.server import app  # noqa: PLC0415 — legacy import must happen after sys.path setup
    return app


def main():
    if not DDL_PATH.exists():
        driver.fail(f"DDL not found at {DDL_PATH} — run P5 contract extraction first")
    corpus_files = sorted(CORPUS_DIR.glob("*.requests.jsonl"))
    if not corpus_files:
        driver.fail(f"no corpus files found under {CORPUS_DIR}")
    total = 0
    # legacy/app/server.py:14 hardcodes DB_PATH = "db/ticketd.sqlite3" — a path relative to the
    # process CWD, resolved at each sqlite3.connect() call, not at import time (see
    # docs/contracts/integration-notes.md). So the harness must chdir into a scratch directory
    # with a "db/" subdir matching that hardcoded relative path — legacy/ itself stays untouched
    # (it's chmod read-only; the app never writes into legacy/, its SQLITE_DB_PATH is scratch).
    orig_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        (scratch / "db").mkdir()
        os.chdir(scratch)
        try:
            app = load_legacy_app()
            db_path = scratch / "db" / "ticketd.sqlite3"
            for cf in corpus_files:
                feature = cf.name.replace(".requests.jsonl", "")
                specs = driver.load_corpus(cf)
                traces = [driver.run_one_legacy(app, db_path, spec, DDL_PATH) for spec in specs]
                out_path = TRACES_DIR / f"{feature}.legacy.jsonl"
                driver.write_traces(out_path, traces)
                print(f"{feature}: {len(traces)} traces -> {out_path.relative_to(ROOT)}")
                total += len(traces)
        finally:
            os.chdir(orig_cwd)
    print(f"legacy golden generation complete: {total} traces across {len(corpus_files)} feature(s)")


if __name__ == "__main__":
    main()
