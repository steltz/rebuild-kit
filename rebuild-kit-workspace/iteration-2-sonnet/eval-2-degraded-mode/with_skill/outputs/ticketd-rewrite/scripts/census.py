#!/usr/bin/env python3
"""P6 dirty-data census generator: parse DDL (CREATE TABLE) and emit probing SQL for the
standard dirt taxonomy — nulls in required columns, orphaned FKs, out-of-range enums,
duplicates under unique intent, timezone-naive datetimes, encoding anomalies.

Usage: census.py --ddl DDL_FILE [--root ROOT] [--dialect postgres|mysql|sqlite]
Writes docs/migration/census-queries.sql and a census.md skeleton for the results.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rk_common import die, find_root

TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\((.*?)\)\s*;",
                      re.IGNORECASE | re.DOTALL)
FK_RE = re.compile(r"FOREIGN\s+KEY\s*\(\s*[`\"]?(\w+)[`\"]?\s*\)\s*REFERENCES\s+[`\"]?(\w+)[`\"]?"
                   r"\s*\(\s*[`\"]?(\w+)[`\"]?\s*\)", re.IGNORECASE)
COL_FK_RE = re.compile(r"REFERENCES\s+[`\"]?(\w+)[`\"]?\s*\(\s*[`\"]?(\w+)[`\"]?\s*\)", re.IGNORECASE)
CHECK_IN_RE = re.compile(r"CHECK\s*\(\s*[`\"]?(\w+)[`\"]?\s+IN\s*\(([^)]*)\)", re.IGNORECASE)


def split_cols(body):
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def parse_ddl(text):
    tables = {}
    for m in TABLE_RE.finditer(text):
        name, body = m.group(1), m.group(2)
        cols, fks, uniques, enums = [], [], [], {}
        for part in split_cols(body):
            up = part.upper()
            fk = FK_RE.search(part)
            if fk:
                fks.append((fk.group(1), fk.group(2), fk.group(3)))
                continue
            if up.startswith(("PRIMARY KEY", "CONSTRAINT", "KEY ", "INDEX ", "UNIQUE")):
                if up.startswith("UNIQUE"):
                    cols_in = re.search(r"\(([^)]*)\)", part)
                    if cols_in:
                        uniques.append([c.strip(" `\"") for c in cols_in.group(1).split(",")])
                continue
            cm = re.match(r"[`\"]?(\w+)[`\"]?\s+(\w+)", part)
            if not cm:
                continue
            col, ctype = cm.group(1), cm.group(2).lower()
            colfk = COL_FK_RE.search(part)
            if colfk:
                fks.append((col, colfk.group(1), colfk.group(2)))
            chk = CHECK_IN_RE.search(part)
            if chk:
                enums[chk.group(1)] = chk.group(2)
            cols.append({"name": col, "type": ctype,
                         "not_null": "NOT NULL" in up or "PRIMARY KEY" in up,
                         "unique": "UNIQUE" in up and "(" not in part.split("UNIQUE")[0]})
            if cols[-1]["unique"]:
                uniques.append([col])
        tables[name] = {"cols": cols, "fks": fks, "uniques": uniques, "enums": enums}
    return tables


TEXTY = ("char", "text", "varchar", "string", "citext")
DATEY = ("timestamp", "datetime", "date")


def queries_for(table, t):
    out = []
    for c in t["cols"]:
        if c["not_null"]:
            out.append((f"nulls in required column {table}.{c['name']}",
                        f"SELECT COUNT(*) FROM {table} WHERE {c['name']} IS NULL;"))
        if any(k in c["type"] for k in TEXTY):
            out.append((f"encoding anomalies / control chars in {table}.{c['name']}",
                        f"SELECT COUNT(*) FROM {table} WHERE {c['name']} ~ '[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F]' "
                        f"OR {c['name']} <> TRIM({c['name']});  -- postgres syntax; adapt per dialect"))
        if any(k in c["type"] for k in DATEY) and "tz" not in c["type"]:
            out.append((f"timezone-naive / out-of-range datetimes in {table}.{c['name']}",
                        f"SELECT MIN({c['name']}), MAX({c['name']}), COUNT(*) FROM {table} "
                        f"WHERE {c['name']} < '1990-01-01' OR {c['name']} > '2100-01-01';"))
    for col, reft, refc in t["fks"]:
        out.append((f"orphaned FK {table}.{col} → {reft}.{refc}",
                    f"SELECT COUNT(*) FROM {table} c LEFT JOIN {reft} p ON c.{col} = p.{refc} "
                    f"WHERE c.{col} IS NOT NULL AND p.{refc} IS NULL;"))
    for ucols in t["uniques"]:
        cl = ", ".join(ucols)
        out.append((f"duplicates under unique intent {table}({cl})",
                    f"SELECT {cl}, COUNT(*) FROM {table} GROUP BY {cl} HAVING COUNT(*) > 1;"))
    for col, vals in t["enums"].items():
        out.append((f"out-of-range enum values in {table}.{col}",
                    f"SELECT {col}, COUNT(*) FROM {table} WHERE {col} NOT IN ({vals}) GROUP BY {col};"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ddl", required=True)
    ap.add_argument("--root")
    ap.add_argument("--dialect", default="postgres")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else find_root()
    if not root:
        die("no rebuild.json found — run scaffold.py first")
    ddl_path = Path(args.ddl)
    if not ddl_path.is_absolute():
        ddl_path = root / ddl_path
    tables = parse_ddl(ddl_path.read_text())
    if not tables:
        die(f"no CREATE TABLE statements parsed from {ddl_path}")

    out = root / "docs" / "migration"
    out.mkdir(parents=True, exist_ok=True)
    sql, md = [f"-- Dirty-data census ({args.dialect}); generated from {args.ddl}",
               "-- Run read-only against prod-shaped data; paste counts into census.md.", ""], \
              ["# Data Census", "", f"Tables: {len(tables)} · queries generated from `{args.ddl}`",
               "", "| # | probe | count | scrubbed sample | policy (ASK until ratified) |",
               "|---|---|---|---|---|"]
    n = 0
    for table, t in tables.items():
        sql.append(f"-- ==== {table} ====")
        for desc, q in queries_for(table, t):
            n += 1
            sql += [f"-- [{n}] {desc}", q, ""]
            md.append(f"| {n} | {desc} | | | ASK |")
    (out / "census-queries.sql").write_text("\n".join(sql))
    (out / "census.md").write_text("\n".join(md) + "\n\n"
        "<!-- Policies per dirty class: repair | quarantine | drop-with-log — ASK items until "
        "a human ratifies (see phases/P6-data-census.md). -->\n")

    print(f"{n} census queries across {len(tables)} tables → {out / 'census-queries.sql'}")
    print("Next: have a human (or granted read-only connection) run them; record counts + "
          "scrubbed samples in census.md; draft mapping.md with per-class policies as ASKs.")


if __name__ == "__main__":
    main()
