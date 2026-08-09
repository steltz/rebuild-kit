#!/usr/bin/env python3
"""P5 fixture validator: checks docs/contracts/fixtures/*.json against the component schemas
embedded in docs/contracts/openapi.yaml. Stdlib only (no pip installs required) -- reuses this
directory's own replay.py load_yaml unmodified (openapi.yaml is deliberately written in plain
block style, no inline "{...}" flow mappings, no ">"/"|" block scalars, specifically so it stays
inside that reader's restricted subset -- see the file-format note at the top of openapi.yaml).

Implements a small hand-rolled JSON-Schema-subset checker (type/required/properties/enum/oneOf/
nullable/additionalProperties/items -- everything this app's schemas actually use; not a general
validator, matches replay.py's own "keep it simple, stdlib" philosophy).

Usage: python3 scripts/validate_fixtures.py   (run from the rewrite root)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from replay import load_yaml  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "docs/contracts/fixtures"

PY_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
            "integer": int, "number": (int, float), "null": type(None)}


def unquote_keys(obj):
    """replay.py's load_yaml strips quotes from scalar VALUES but not from dict KEYS (never
    needed to, for its own diff-rules.yaml/expected-divergences.yaml -- neither quotes a key).
    openapi.yaml quotes response-code keys ("200", "201", ...) per OpenAPI/JSON-Schema
    convention (keeps YAML from coercing them to ints, which real tooling also cares about --
    see the docstring above). Post-process here rather than touch the bundled parser."""
    if isinstance(obj, dict):
        return {(k[1:-1] if isinstance(k, str) and k.startswith('"') and k.endswith('"') else k):
                unquote_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [unquote_keys(v) for v in obj]
    return obj


def resolve(schema, components):
    """Resolve local $refs and translate OpenAPI's `nullable: true` into a type union."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            return resolve(components[schema["$ref"].split("/")[-1]], components)
        out = {k: resolve(v, components) for k, v in schema.items() if k != "nullable"}
        if schema.get("nullable") and "type" in out:
            t = out["type"]
            out["type"] = (t if isinstance(t, list) else [t]) + ["null"]
        return out
    if isinstance(schema, list):
        return [resolve(v, components) for v in schema]
    return schema


def check(instance, schema, path="$"):
    """Returns a list of error strings; empty means valid."""
    errs = []
    if "oneOf" in schema:
        sub_errs = [check(instance, s, path) for s in schema["oneOf"]]
        if all(sub_errs):  # every branch failed
            errs.append(f"{path}: matched none of {len(schema['oneOf'])} oneOf branches "
                        f"(first branch errors: {sub_errs[0]})")
        return errs
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        py_types = tuple(PY_TYPES[t] for t in types)
        if "boolean" in types and "integer" not in types:
            ok = isinstance(instance, bool) or (type(None) in py_types and instance is None)
        else:
            ok = isinstance(instance, py_types) and not (
                isinstance(instance, bool) and "integer" in types and "boolean" not in types)
        if not ok:
            errs.append(f"{path}: expected type {types}, got {type(instance).__name__}")
            return errs
    if "enum" in schema:
        enum_vals = schema["enum"]
        # Known replay.py load_yaml quirk: it strips quotes THEN tries int/float conversion, so
        # a quoted numeric string like "1" in YAML comes back as the Python int 1, not str "1"
        # (see PriorityDigit in openapi.yaml -- confirmed by reading load_yaml's scalar()). For
        # a schema declared `type: string`, compare stringified forms so this doesn't produce a
        # false FAIL; the real OpenAPI file is unambiguous (validated separately against real
        # tooling), this is purely a limitation of the bundled stdlib-only reader.
        if schema.get("type") == "string":
            ok = str(instance) in [str(e) for e in enum_vals]
        else:
            ok = instance in enum_vals
        if not ok:
            errs.append(f"{path}: {instance!r} not in enum {enum_vals}")
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required property '{req}'")
        props = schema.get("properties", {})
        for k, v in instance.items():
            if k in props:
                errs += check(v, props[k], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}.{k}: additional property not allowed")
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errs += check(item, schema["items"], f"{path}[{i}]")
    return errs


def main():
    spec = unquote_keys(load_yaml(ROOT / "docs/contracts/openapi.yaml"))
    components = spec["components"]["schemas"]

    def schema_at(*keys):
        cur = spec
        for k in keys:
            cur = cur[k]
        return resolve(cur, components)

    checks = [
        ("ticket-create-request.json",
         schema_at("paths", "/api/tickets", "post", "requestBody", "content", "application/json", "schema")),
        ("ticket-create-response.json",
         schema_at("paths", "/api/tickets", "post", "responses", "201", "content", "application/json", "schema")),
        ("ticket-get-found.json", resolve({"$ref": "#/components/schemas/Ticket"}, components)),
        ("ticket-get-not-found.json",
         schema_at("paths", "/api/tickets/{tid}", "get", "responses", "200", "content", "application/json", "schema")),
        ("ticket-list-response.json",
         schema_at("paths", "/api/tickets", "get", "responses", "200", "content", "application/json", "schema")),
        ("ticket-close-response.json",
         schema_at("paths", "/api/tickets/{tid}/close", "post", "responses", "200", "content", "application/json", "schema")),
        ("reset-request-response.json",
         schema_at("paths", "/api/auth/reset", "post", "responses", "200", "content", "application/json", "schema")),
        ("reset-rate-limited-response.json",
         schema_at("paths", "/api/auth/reset", "post", "responses", "429", "content", "application/json", "schema")),
        ("reset-confirm-response.json",
         schema_at("paths", "/api/auth/reset/confirm", "post", "responses", "200", "content", "application/json", "schema")),
        ("reset-invalid-token-response.json",
         schema_at("paths", "/api/auth/reset/confirm", "post", "responses", "403", "content", "application/json", "schema")),
    ]

    results = []
    for fname, schema in checks:
        instance = json.loads((FX / fname).read_text())
        errs = check(instance, schema)
        results.append(f"{'PASS' if not errs else 'FAIL'}  {fname}" + ("" if not errs else f": {errs}"))

    # export-csv-response.csv: not JSON -- structural check only (header + column count)
    csv_lines = (FX / "export-csv-response.csv").read_text().strip().splitlines()
    header_ok = csv_lines[0] == "id,title,status"
    rows_ok = all(len(line.split(",")) == 3 for line in csv_lines)
    results.append(f"{'PASS' if header_ok and rows_ok else 'FAIL'}  export-csv-response.csv "
                   "(header + 3-column structural check)")

    print("\n".join(results))
    sys.exit(0 if all(r.startswith("PASS") for r in results) else 1)


if __name__ == "__main__":
    main()
