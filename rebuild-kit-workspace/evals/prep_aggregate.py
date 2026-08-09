#!/usr/bin/env python3
"""Prepare an iteration directory for scripts.aggregate_benchmark.

Two shape mismatches to reconcile:

1. The aggregator reads grading + timing from `<config>/run-N/`, while run_arm.py
   writes one run per config directly. This mirrors them into `run-1/`.
2. run_arm.py records `total_tokens` as the raw usage object from the CLI result
   record; the aggregator expects a scalar and would otherwise average dicts.
   This sums input+output (plus cache reads, which are real spend) into an int
   and preserves the original under `usage`.

Usage: prep_aggregate.py <iteration-dir>
"""
import json
import sys
from pathlib import Path


def scalar_tokens(usage):
    if isinstance(usage, int):
        return usage
    if not isinstance(usage, dict):
        return 0
    return int(
        usage.get("input_tokens", 0)
        + usage.get("output_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )


def main():
    it = Path(sys.argv[1]).resolve()
    fixed = []
    for cfg_dir in sorted(it.glob("eval-*/*")):
        if not cfg_dir.is_dir() or cfg_dir.name.startswith("run-"):
            continue
        grading = cfg_dir / "grading.json"
        timing = cfg_dir / "timing.json"
        if not grading.exists():
            print(f"  skip (no grading.json): {cfg_dir.relative_to(it)}")
            continue

        g = json.loads(grading.read_text())
        # The aggregator pulls timing from timing.json only when grading.json
        # carries none; stray blocks here silently win over the real numbers.
        g.pop("timing", None)
        g.pop("execution_metrics", None)
        grading.write_text(json.dumps(g, indent=2))

        run1 = cfg_dir / "run-1"
        run1.mkdir(exist_ok=True)
        (run1 / "grading.json").write_text(json.dumps(g, indent=2))

        if timing.exists():
            t = json.loads(timing.read_text())
            usage = t.get("total_tokens")
            if not isinstance(usage, int):
                t["usage"] = usage
                t["total_tokens"] = scalar_tokens(usage)
            t.setdefault("total_duration_seconds",
                         round((t.get("duration_ms") or t.get("wall_ms") or 0) / 1000, 1))
            timing.write_text(json.dumps(t, indent=2))
            (run1 / "timing.json").write_text(json.dumps(t, indent=2))
        fixed.append(str(cfg_dir.relative_to(it)))
    print(f"prepared {len(fixed)} arms: {fixed}")


if __name__ == "__main__":
    main()
