#!/usr/bin/env python3
"""PreToolUse guard for eval executor agents.

Two jobs:

1. Audit. Append every tool call to $RK_AUDIT_LOG so grading a run for
   contamination is a mechanical check over JSONL instead of a human reading a
   transcript and hoping they spot it.

2. Block the one leak the kernel sandbox cannot close. The sandbox profile makes
   the skill unreadable on local disk, but the skill is also a pushed git remote,
   so a baseline agent could in principle fetch it over the network. Tool calls
   that look like remote retrieval of the skill repo are denied here.

Configured via env (set by run_arm.py):
  RK_AUDIT_LOG   path to the JSONL audit log
  RK_GUARD_MODE  "block" (baseline arm) or "audit" (with-skill arm; log only)
"""
import json
import os
import re
import sys

# Remote retrieval of the skill repo. The local filesystem is handled by the
# sandbox profile; these patterns cover only what crosses the network.
REMOTE_PATTERNS = [
    re.compile(r"github\.com[:/][\w.-]+/rebuild-kit", re.I),
    re.compile(r"\bgit\s+(clone|fetch|pull|archive)\b[^\n]*rebuild-kit", re.I),
    re.compile(r"\bgh\s+(repo|api|release)\b[^\n]*rebuild-kit", re.I),
    re.compile(r"\b(curl|wget|http[s]?_proxy)\b[^\n]*rebuild-kit", re.I),
]

# Not blocked — reads are already kernel-denied — but worth flagging for the
# grader, because an agent that tried these was actively hunting for the skill.
PROBE_PATTERNS = [
    re.compile(r"\bmdfind\b", re.I),
    re.compile(r"\blocate\b", re.I),
    re.compile(r"rebuild.kit", re.I),
    re.compile(r"render_guide", re.I),
]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never wedge a run on a malformed event

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    haystack = json.dumps(tool_input, ensure_ascii=False)

    remote_hits = [p.pattern for p in REMOTE_PATTERNS if p.search(haystack)]
    probe_hits = [p.pattern for p in PROBE_PATTERNS if p.search(haystack)]
    mode = os.environ.get("RK_GUARD_MODE", "audit")
    blocked = bool(remote_hits) and mode == "block"

    log_path = os.environ.get("RK_AUDIT_LOG")
    if log_path:
        record = {
            "tool": tool_name,
            "input": haystack[:4000],
            "remote_hits": remote_hits,
            "probe_hits": probe_hits,
            "blocked": blocked,
        }
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    if blocked:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Blocked by eval isolation: this run's arm may not retrieve "
                        "the rebuild-kit skill from a remote."
                    ),
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
