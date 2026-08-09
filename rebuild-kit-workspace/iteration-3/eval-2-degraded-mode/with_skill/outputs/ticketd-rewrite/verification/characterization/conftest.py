"""Shared fixtures for L2 characterization tests. These test modern/, not legacy/ — legacy's
own behavior is already pinned as the golden traces under verification/replay/traces/*.legacy.jsonl
(L3). Skips cleanly (not an error) until modern/app/main.py + testing.py exist — see
verification/harness/run_modern.py's docstring for that contract.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODERN_MAIN = ROOT / "modern" / "app" / "main.py"
MODERN_TESTING = ROOT / "modern" / "app" / "testing.py"
FIXTURES_DIR = ROOT / "docs" / "contracts" / "fixtures"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def client():
    if not MODERN_MAIN.exists() or not MODERN_TESTING.exists():
        pytest.skip("modern/app/main.py or modern/app/testing.py not implemented yet (pre-M0)")
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    main_mod = _load(MODERN_MAIN, "modern_main")
    testing_mod = _load(MODERN_TESTING, "modern_testing")
    testing_mod.reset_and_seed(None)
    return fastapi_testclient.TestClient(main_mod.app)


@pytest.fixture
def seed():
    if not MODERN_TESTING.exists():
        pytest.skip("modern/app/testing.py not implemented yet (pre-M0)")
    testing_mod = _load(MODERN_TESTING, "modern_testing")
    return testing_mod.reset_and_seed


def load_fixture(name):
    import json
    return json.loads((FIXTURES_DIR / name).read_text())
