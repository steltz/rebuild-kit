#!/usr/bin/env python3
"""Boot modern/ against each corpus file and record a MODERN trace to
verification/replay/traces/<feature>.modern.jsonl, for diffing against the cached legacy golden.

modern/ is empty at generation time (P7 runs before any WO is implemented) — this script is
built now so the harness twin-boots from day one of execution (rebuild-kit design principle),
but it necessarily finds nothing to boot yet. That is expected, not a defect: it prints a clear
status and writes empty trace files per feature, so diff-run.sh's report is legible pre-M0
rather than a stack trace.

Contract this script expects modern/ to eventually provide (document, don't build — that's the
executor's job per a future WO, since it depends on the FastAPI app's actual shape):
  - `modern/app/main.py` exporting a FastAPI instance named `app`.
  - `modern/app/testing.py` exporting:
      reset_and_seed(seed_rows) -> None   # mirrors driver.fresh_sqlite_db + seed_db for Postgres
      dump_state() -> dict                # table dumps, shaped like driver.dump_db's output,
                                           # plus an "email_dispatch" list shaped like
                                           # RecordingSMTP's log (see lib/driver.py) so existing
                                           # diff-rules.yaml normalization applies unchanged.
This keeps the twin-boot symmetric without hardcoding a DB driver choice here (FREE per
modern/CLAUDE.md — SQLAlchemy vs asyncpg is the executor's call).
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verification" / "harness" / "lib"))
import driver  # noqa: E402

REBUILD_JSON = json.loads((ROOT / "rebuild.json").read_text())
MODERN_DIR = ROOT / REBUILD_JSON["layout"]["modern_dir"]
CORPUS_DIR = ROOT / "verification" / "replay" / "corpus"
TRACES_DIR = ROOT / "verification" / "replay" / "traces"


def try_load_modern():
    main_path = MODERN_DIR / "app" / "main.py"
    testing_path = MODERN_DIR / "app" / "testing.py"
    if not main_path.exists() or not testing_path.exists():
        return None, "modern/app/main.py or modern/app/testing.py not found — not implemented yet"
    try:
        spec = importlib.util.spec_from_file_location("modern_main", main_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        spec2 = importlib.util.spec_from_file_location("modern_testing", testing_path)
        testing_mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(testing_mod)
        if not hasattr(mod, "app"):
            return None, "modern/app/main.py has no `app` attribute"
        return (mod.app, testing_mod), None
    except Exception as e:  # noqa: BLE001 — boot failures are reported, not raised
        return None, f"modern app failed to import/boot: {e!r}"


def _exec_modern_request(client, req):
    resp = client.request(req["method"], req["path"], headers=req.get("headers") or {},
                           json=req.get("json"))
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return {"status": resp.status_code, "headers": dict(resp.headers), "body": body}


def run_one_modern(app_and_testing, trace_spec):
    """Mirrors driver.run_one_legacy's single-request / multi-step ("steps") shape so
    scripts/replay.py's structural diff lines up field-for-field against the legacy golden."""
    app, testing_mod = app_and_testing
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        driver.fail("fastapi[testclient] (httpx) not installed in this environment")
    testing_mod.reset_and_seed(trace_spec.get("seed_rows"))
    client = TestClient(app)
    if "steps" in trace_spec:
        responses = [_exec_modern_request(client, step["request"]) for step in trace_spec["steps"]]
        state = testing_mod.dump_state()
        return {"id": trace_spec["id"],
                "steps": [{"request": s["request"], "response": r}
                          for s, r in zip(trace_spec["steps"], responses)],
                "state": state}
    req = trace_spec["request"]
    response = _exec_modern_request(client, req)
    state = testing_mod.dump_state()
    return {"id": trace_spec["id"], "request": req, "response": response, "state": state}


def main():
    corpus_files = sorted(CORPUS_DIR.glob("*.requests.jsonl"))
    if not corpus_files:
        driver.fail(f"no corpus files found under {CORPUS_DIR}")
    loaded, reason = try_load_modern()
    if loaded is None:
        print(f"MODERN NOT YET BOOTABLE: {reason}")
        print("Writing empty modern trace files (expected pre-implementation state).")
        for cf in corpus_files:
            feature = cf.name.replace(".requests.jsonl", "")
            out_path = TRACES_DIR / f"{feature}.modern.jsonl"
            driver.write_traces(out_path, [])
            print(f"{feature}: 0 traces -> {out_path.relative_to(ROOT)} (modern not implemented)")
        return
    total = 0
    for cf in corpus_files:
        feature = cf.name.replace(".requests.jsonl", "")
        specs = driver.load_corpus(cf)
        traces = [run_one_modern(loaded, spec) for spec in specs]
        out_path = TRACES_DIR / f"{feature}.modern.jsonl"
        driver.write_traces(out_path, traces)
        print(f"{feature}: {len(traces)} traces -> {out_path.relative_to(ROOT)}")
        total += len(traces)
    print(f"modern trace generation complete: {total} traces across {len(corpus_files)} feature(s)")


if __name__ == "__main__":
    main()
