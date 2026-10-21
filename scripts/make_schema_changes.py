"""Build SchemaShift variants of one BIRD database and the tasks to test LLMs on them.

Each variant is a copy of the original database with one kind of planned schema change.
Every gold query that touches a changed part becomes a task (the old query plus the new
database). The gold answer is worked out automatically:
  - rename, opaque and split keep all the data, so the gold answer is the old query's
    result on the ORIGINAL database;
  - softdelete only marks rows as deleted, so the gold answer is the old query's result on
    a copy where those rows are really deleted.
The original database is opened read-only and never changed.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\make_schema_changes.py data\\bird_minidev\\minidev\\MINIDEV student_club data\\schemashift
"""
import json
import random
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import sqlglot
from sqlglot import exp

# The same six columns are renamed naturally ("rename") and to legacy-style generic names
# ("opaque"), so the two results can be compared directly.
PLANS = {
    "student_club": {
        "rename": {
            "event.event_name": "title",
            "member.first_name": "given_name",
            "member.last_name": "family_name",
            "expense.cost": "amount_spent",
            "budget.link_to_event": "event_id",
            "major.major_name": "name",
        },
        "opaque": {
            "event.event_name": "Attribute1",
            "member.first_name": "Attribute1",
            "member.last_name": "Attribute2",
            "expense.cost": "Attribute1",
            "budget.link_to_event": "Attribute1",
            "major.major_name": "Attribute1",
        },
        # table -> (new table, columns moved into it); rows are linked by the table's primary key
        "split": {
            "member": ("member_contact", ["first_name", "last_name", "email", "phone"]),
            "budget": ("budget_figures", ["spent", "remaining", "amount"]),
        },
        # 15% gave only 7 silently wrong old queries out of 40; 30% gives enough to measure
        "softdelete": {"tables": ["member", "event"], "share": 0.30, "seed": 7},
    },
}

# One-line notes for the "with hint" condition; they say what kind of change happened, not where.
HINTS = {
    "rename": "Some columns were renamed.",
    "opaque": "Some columns were renamed to generic names such as Attribute1.",
    "split": "Some columns were moved into new tables that share the original table's primary key.",
    "softdelete": "Rows with is_deleted = 1 have been deleted and must be ignored.",
}


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(path)


def load_schema(con: sqlite3.Connection) -> dict:
    """{table: {"columns": [...], "types": {...}, "pk": column}}, table names in lower case."""
    schema = {}
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        info = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        schema[table.lower()] = {
            "columns": [c[1] for c in info],
            "types": {c[1]: c[2] for c in info},
            "pk": next((c[1] for c in info if c[5] == 1), None),
        }
    return schema


def column_refs(tree: exp.Expression, schema: dict) -> list:
    """(column node, 'table.column') for every column in the query; None when it cannot be resolved."""
    alias = {t.alias_or_name.lower(): t.name.lower() for t in tree.find_all(exp.Table)}
    in_query = set(alias.values())
    refs = []
    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if col.table:
            table = alias.get(col.table.lower())
        else:
            owners = [t for t in in_query if t in schema and name in (c.lower() for c in schema[t]["columns"])]
            table = owners[0] if len(owners) == 1 else None
        refs.append((col, f"{table}.{name}" if table else None))
    return refs


def touched(sql: str, schema: dict) -> tuple:
    """Tables and 'table.column' names a query reads; SELECT * counts as every column."""
    tree = sqlglot.parse_one(sql, read="sqlite")
    tables = {t.name.lower() for t in tree.find_all(exp.Table)}
    cols = {key for _, key in column_refs(tree, schema) if key and not key.endswith(".*")}
    stars = [col for col in tree.find_all(exp.Column) if col.name == "*"]
    if stars or any(isinstance(e, exp.Star) for s in tree.find_all(exp.Select) for e in s.expressions):
        cols |= {f"{t}.{c.lower()}" for t in tables if t in schema for c in schema[t]["columns"]}
    return tables, cols


def rename_columns(sql: str, mapping: dict, schema: dict) -> str:
    """Reference rewrite of a query for the rename/opaque variants (used to check the variant)."""
    tree = sqlglot.parse_one(sql, read="sqlite")
    for col, key in column_refs(tree, schema):
        if key in mapping:
            col.set("this", exp.to_identifier(mapping[key]))
    return tree.sql(dialect="sqlite")


def make_rename(src: Path, dst: Path, mapping: dict) -> None:
    shutil.copyfile(src, dst)
    con = connect(dst)
    for key, new_name in mapping.items():
        table, column = key.split(".")
        con.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{column}" TO "{new_name}"')
    con.commit()
    con.close()


def make_split(src: Path, dst: Path, plan: dict, schema: dict) -> None:
    shutil.copyfile(src, dst)
    con = connect(dst)
    for table, (new_table, moved) in plan.items():
        info, key = schema[table], schema[table]["pk"]
        defs = ", ".join(f'"{c}" {info["types"][c]}' for c in moved)
        con.execute(f'CREATE TABLE "{new_table}" ("{key}" {info["types"][key]} PRIMARY KEY '
                    f'REFERENCES "{table}"("{key}"), {defs})')
        col_list = ", ".join(f'"{c}"' for c in [key] + moved)
        con.execute(f'INSERT INTO "{new_table}" ({col_list}) SELECT {col_list} FROM "{table}"')
        for column in moved:
            con.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')
    con.commit()
    con.close()


def make_softdelete(src: Path, dst: Path, gold_dst: Path, plan: dict, schema: dict) -> dict:
    """Mark a seeded random share of rows as deleted; the gold copy deletes them for real."""
    rng = random.Random(plan["seed"])
    shutil.copyfile(src, dst)
    shutil.copyfile(src, gold_dst)
    con, gold = connect(dst), connect(gold_dst)
    deleted = {}
    for table in plan["tables"]:
        key = schema[table]["pk"]
        ids = sorted(r[0] for r in con.execute(f'SELECT "{key}" FROM "{table}"'))
        chosen = sorted(rng.sample(ids, round(len(ids) * plan["share"])))
        marks = ", ".join("?" * len(chosen))
        con.execute(f'ALTER TABLE "{table}" ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0')
        con.execute(f'UPDATE "{table}" SET is_deleted = 1 WHERE "{key}" IN ({marks})', chosen)
        gold.execute(f'DELETE FROM "{table}" WHERE "{key}" IN ({marks})', chosen)
        deleted[table] = chosen
    for c in (con, gold):
        c.commit()
        c.close()
    return deleted


def split_keeps_data(orig: sqlite3.Connection, variant: sqlite3.Connection, plan: dict, schema: dict) -> bool:
    """Joining the split tables back together must give exactly the original rows."""
    for table, (new_table, moved) in plan.items():
        cols, key = schema[table]["columns"], schema[table]["pk"]
        before = orig.execute("SELECT " + ", ".join(f'"{c}"' for c in cols) + f' FROM "{table}"').fetchall()
        rebuilt = ", ".join((f'n."{c}"' if c in moved else f't."{c}"') for c in cols)
        after = variant.execute(f'SELECT {rebuilt} FROM "{table}" AS t JOIN "{new_table}" AS n '
                                f'ON t."{key}" = n."{key}"').fetchall()
        if Counter(before) != Counter(after):
            return False
    return True


def same_result(a: list, b: list) -> bool:
    """BIRD compares results as sets of rows."""
    return set(a) == set(b)


def write_schema(db: Path) -> None:
    con = connect(db, readonly=True)
    ddl = [r[0] + ";" for r in con.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    con.close()
    db.with_suffix(".schema.sql").write_text("\n\n".join(ddl) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: make_schema_changes.py <MINIDEV folder> <db_id> <output folder>")
    root, db_id, out = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve() / sys.argv[2]
    if db_id not in PLANS:
        sys.exit(f"No change plan for {db_id}; add one to PLANS.")
    plan = PLANS[db_id]
    src = root / "dev_databases" / db_id / f"{db_id}.sqlite"
    out.mkdir(parents=True, exist_ok=True)
    questions = [q for q in json.loads((root / "mini_dev_sqlite.json").read_text(encoding="utf-8"))
                 if q["db_id"] == db_id]

    orig = connect(src, readonly=True)
    schema = load_schema(orig)
    dbs = {op: out / f"{op}.sqlite" for op in ("rename", "opaque", "split", "softdelete")}
    gold_db = out / "softdelete_gold.sqlite"
    make_rename(src, dbs["rename"], plan["rename"])
    make_rename(src, dbs["opaque"], plan["opaque"])
    make_split(src, dbs["split"], plan["split"], schema)
    deleted = make_softdelete(src, dbs["softdelete"], gold_db, plan["softdelete"], schema)
    for db in dbs.values():
        write_schema(db)

    variants = {op: connect(db, readonly=True) for op, db in dbs.items()}
    gold_con = connect(gold_db, readonly=True)
    split_ok = split_keeps_data(orig, variants["split"], plan["split"], schema)
    moved = {f"{t}.{c}" for t, (_, cols) in plan["split"].items() for c in cols}

    tasks, stats = [], Counter()
    for q in questions:
        tables, cols = touched(q["SQL"], schema)
        hits = {
            "rename": sorted(cols & set(plan["rename"])),
            "opaque": sorted(cols & set(plan["opaque"])),
            "split": sorted(cols & moved),
            "softdelete": sorted(tables & set(plan["softdelete"]["tables"])),
        }
        for op, changes in hits.items():
            if not changes:
                continue
            task = {
                "task_id": f"{db_id}-{q['question_id']}-{op}", "db_id": db_id, "question_id": q["question_id"],
                "difficulty": q.get("difficulty"), "operator": op, "question": q["question"],
                "evidence": q.get("evidence", ""), "old_sql": q["SQL"], "touched_changes": changes,
                "new_db": dbs[op].name, "hint": HINTS[op],
            }
            if op == "softdelete":
                gold = gold_con.execute(q["SQL"]).fetchall()
                task["result_changes"] = not same_result(variants[op].execute(q["SQL"]).fetchall(), gold)
                stats["softdelete_silent"] += task["result_changes"]
            else:
                gold = orig.execute(q["SQL"]).fetchall()
            if op in ("rename", "opaque"):
                task["reference_sql"] = rename_columns(q["SQL"], plan[op], schema)
                ok = same_result(variants[op].execute(task["reference_sql"]).fetchall(), gold)
                stats[f"{op}_reference_ok"] += ok
                if not ok:
                    print(f"WARNING: reference SQL does not match gold for {task['task_id']}")
            task["gold_rows"] = [list(r) for r in gold]
            tasks.append(task)
            stats[op] += 1

    with (out / "tasks.jsonl").open("w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
    changes = {"db_id": db_id, "sqlite_version": sqlite3.sqlite_version, "hints": HINTS,
               "rename": plan["rename"], "opaque": plan["opaque"],
               "split": {t: {"new_table": n, "moved_columns": c} for t, (n, c) in plan["split"].items()},
               "softdelete": {**plan["softdelete"], "deleted_ids": deleted}}
    (out / "changes.json").write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{db_id}: {len(questions)} questions -> {len(tasks)} tasks in {out / 'tasks.jsonl'}")
    for op in ("rename", "opaque"):
        print(f"  {op:<10} {stats[op]:3} tasks  (reference SQL matches gold: {stats[op + '_reference_ok']}/{stats[op]})")
    print(f"  {'split':<10} {stats['split']:3} tasks  (split tables rebuild the original rows: {'yes' if split_ok else 'NO'})")
    print(f"  {'softdelete':<10} {stats['softdelete']:3} tasks  (old query silently wrong in {stats['softdelete_silent']})")
    print(f"  deleted ids: { {t: len(ids) for t, ids in deleted.items()} }")


if __name__ == "__main__":
    main()
