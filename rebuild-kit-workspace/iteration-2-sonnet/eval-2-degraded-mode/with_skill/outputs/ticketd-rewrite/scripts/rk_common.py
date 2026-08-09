"""Shared helpers for rebuild-kit scripts. Stdlib only — no pip dependencies."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
             ".next", ".cache", "vendor", "target", ".tox", ".mypy_cache", "coverage"}

LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".rb": "ruby", ".php": "php", ".go": "go", ".java": "java",
    ".cs": "csharp", ".sql": "sql", ".sh": "shell", ".pl": "perl", ".rs": "rust",
}


def find_root(start=None):
    """Walk up from start (default cwd) looking for rebuild.json. Returns Path or None."""
    p = Path(start or os.getcwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "rebuild.json").is_file():
            return candidate
    return None


def load_layout(root):
    """Return (rebuild_dict, legacy_path, modern_path) for a rewrite root."""
    root = Path(root)
    cfg = json.loads((root / "rebuild.json").read_text())
    legacy = root / cfg["layout"]["legacy_dir"]
    modern = root / cfg["layout"]["modern_dir"]
    return cfg, legacy, modern


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, cwd=None, check=False):
    """Run a command, return (returncode, stdout). Never raises unless check=True."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        die(f"command failed: {' '.join(cmd)}\n{res.stderr.strip()}")
    return res.returncode, res.stdout


def iter_source_files(base):
    """Yield source files under base, skipping vendored/derived trees."""
    base = Path(base)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.suffix in LANG_BY_EXT:
                yield p


# ---------------------------------------------------------------------------
# PII scrubbing — applied at intake, before anything lands in the workspace.
# ---------------------------------------------------------------------------
_PII_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<EMAIL>"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.~+/]+=*"), "Bearer <TOKEN>"),
    (re.compile(r"(?i)\b(token|password|secret|api_?key|auth|session)=([^&\s\"]+)"), r"\1=<REDACTED>"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<HEX>"),
    (re.compile(r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]*"), "<JWT>"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "<PAN?>"),  # possible card numbers
]


def scrub(text):
    for pat, repl in _PII_PATTERNS:
        text = pat.sub(repl, text)
    return text
