#!/usr/bin/env python3
"""P5 validation: round-trip every fixture in fixtures/ against its target schema in
openapi.yaml. Minimal hand-rolled JSON-Schema-subset checker (type, required, enum, nullable) --
sufficient for this app's simple schemas; swap for `jsonschema` if the contracts grow more
complex. Requires PyYAML for openapi.yaml itself (docs/contracts/fixtures/README.md notes this).

Usage: python3 docs/contracts/validate_fixtures.py
Exit code 0 = all fixtures valid, 1 = at least one failure.
"""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml (or use a venv -- see verification/harness/README.md)",
          file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent
SPEC = yaml.safe_load((ROOT / "openapi.yaml").read_text())
SCHEMAS = SPEC["components"]["schemas"]

TARGETS = {
    "ticket.json": "Ticket",
    "create-ticket-request.json": "CreateTicketRequest",
    "create-ticket-response.json": "CreateTicketResponse",
    "error-title-required.json": "ErrorBody",
    "error-invalid-token.json": "ErrorBody",
    # ticket-not-found.json is validated separately below (it's the {} sentinel, not a named schema)
}


def check_type(value, schema, path):
    errors = []
    t = schema.get("type")
    nullable = schema.get("nullable", False)
    if value is None:
        if not nullable and t is not None:
            errors.append(f"{path}: null not allowed (nullable={nullable})")
        return errors
    if t == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return errors
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required field '{req}'")
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                errors += check_type(v, props[k], f"{path}.{k}")
            # extra fields: allowed (no additionalProperties: false declared on these schemas)
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path}: expected integer, got {type(value).__name__}")
    elif t == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")
        enum = schema.get("enum")
        if enum and value not in enum:
            errors.append(f"{path}: '{value}' not in enum {enum}")
    elif "oneOf" in schema:
        sub_errors_all = []
        matched = False
        for sub in schema["oneOf"]:
            sub_errors = check_type(value, sub, path)
            if not sub_errors:
                matched = True
                break
            sub_errors_all.append(sub_errors)
        if not matched:
            errors.append(f"{path}: matched none of the oneOf branches: {sub_errors_all}")
    return errors


def main():
    fixtures_dir = ROOT / "fixtures"
    all_ok = True
    for fname, schema_name in TARGETS.items():
        path = fixtures_dir / fname
        data = json.loads(path.read_text())
        schema = SCHEMAS[schema_name]
        errors = check_type(data, schema, fname)
        if errors:
            all_ok = False
            print(f"FAIL {fname} vs {schema_name}:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"PASS {fname} vs {schema_name}")

    # ticket-not-found.json: validated against the documented empty-object sentinel, not a
    # named component schema (it's inline in the GET /api/tickets/{id} 200 response, oneOf
    # branch 2 in openapi.yaml).
    nf = json.loads((fixtures_dir / "ticket-not-found.json").read_text())
    if nf == {}:
        print("PASS ticket-not-found.json vs inline empty-object sentinel (GET /api/tickets/{id})")
    else:
        all_ok = False
        print(f"FAIL ticket-not-found.json: expected {{}}, got {nf}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
