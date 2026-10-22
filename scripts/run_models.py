"""Ask a model to adapt each SchemaShift task to the changed database, run its SQL, and score it.

Works with any OpenAI-compatible chat endpoint: Ollama (the default,
http://127.0.0.1:11434/v1), vLLM on Colab, or a hosted API. Two baselines need no model:
  old-query  change nothing (how often the old query is still right, or silently wrong)
  reference  the scripted rewrite from make_schema_changes.py (rename/opaque only; should score 100%)
Results go to results/<db>__<model>__<mode>[__hint].jsonl, one line per task. An interrupted
run continues where it stopped.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\run_models.py data\\schemashift\\student_club --model old-query
    .venv\\Scripts\\python.exe -I scripts\\run_models.py data\\schemashift\\student_club --model qwen2.5-coder:7b --limit 10
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off sys.path
from make_schema_changes import column_refs, load_schema  # noqa: E402

SYSTEM = "You are an expert SQLite developer."
OPERATORS = ("rename", "opaque", "split", "softdelete")


def run_name(db_id: str, model: str, mode: str, hint: bool) -> str:
    """File name stem of a run's results, e.g. student_club__qwen2.5-coder-7b__adapt__hint."""
    slug = re.sub(r"[^A-Za-z0-9.]+", "-", model).strip("-")
    return f"{db_id}__{slug}__{mode}{'__hint' if hint else ''}"


def open_ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def schema_text(db: Path, rows: int) -> str:
    """CREATE TABLE statements, each followed by a few example rows."""
    con = open_ro(db)
    blocks = []
    for name, ddl in con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        block = ddl.strip() + ";"
        if rows:
            cur = con.execute(f'SELECT * FROM "{name}" LIMIT {rows}')
            lines = [" | ".join(d[0] for d in cur.description)]
            lines += [" | ".join(str(v)[:40] for v in row) for row in cur.fetchall()]
            block += f"\n/* {rows} example rows from {name}:\n" + "\n".join(lines) + "\n*/"
        blocks.append(block)
    con.close()
    return "\n\n".join(blocks)


def build_prompt(task: dict, schema: str, mode: str, hint: bool) -> str:
    note = f"Note: {task['hint']}\n\n" if hint else ""
    if mode == "adapt":
        return ("A database was changed, and the SQL query below was written for the old version.\n"
                "Rewrite the query so that it runs on the new database and returns the information "
                "it was written to return.\n\n"
                f"{note}New database schema (SQLite), with example rows:\n{schema}\n\n"
                f"Old query:\n{task['old_sql']}\n\n"
                "Answer with only the rewritten SQL query in a ```sql code block.")
    return ("Write a SQLite query that answers the question below on this database.\n\n"
            f"{note}Database schema (SQLite), with example rows:\n{schema}\n\n"
            f"Question: {task['question']}\n\n"
            "Answer with only the SQL query in a ```sql code block.")


def ask(base_url: str, model: str, api_key: str, prompt: str, max_tokens: int, timeout: int) -> str:
    """One chat request to an OpenAI-compatible endpoint, retried on network errors."""
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)["choices"][0]["message"]["content"] or ""
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    return ""


def extract_sql(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # reasoning models think out loud first
    blocks = re.findall(r"```(?:sql|sqlite)?[ \t]*\n?(.*?)```", text, flags=re.S | re.I)
    sql = blocks[-1] if blocks else text
    return sql.strip().rstrip(";").strip()


def execute(db: Path, sql: str, seconds: float = 10.0) -> tuple:
    """Run a query read-only with a time limit; returns (rows, error)."""
    con = open_ro(db)
    deadline = time.monotonic() + seconds
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
    try:
        return con.execute(sql).fetchall(), None
    except Exception as e:  # any SQL error counts as a wrong answer, not a crash
        return None, f"{type(e).__name__}: {e}"
    finally:
        con.close()


def mentions_deleted(sql: str, schema: dict, tables: list):
    """True if the query reads is_deleted on every soft-deleted table it uses; None if unparsable."""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return None
    used = {t.name.lower() for t in tree.find_all(exp.Table)} & set(tables)
    refs = {key for _, key in column_refs(tree, schema) if key}
    return all(f"{t}.is_deleted" in refs for t in used)


def summarise(out_file: Path) -> None:
    records = [json.loads(line) for line in out_file.open(encoding="utf-8")]
    by_op = defaultdict(list)
    for r in records:
        by_op[r["operator"]].append(r)
    summary = {}
    print(f"\n{'operator':<11}{'tasks':>6}{'ran':>6}{'correct':>9}")
    for op in OPERATORS:
        rs = by_op.get(op)
        if not rs:
            continue
        ran, ok = sum(r["error"] is None for r in rs), sum(r["correct"] for r in rs)
        summary[op] = {"tasks": len(rs), "ran_without_error": ran, "correct": ok}
        line = f"{op:<11}{len(rs):>6}{ran:>6}{ok:>6} ({100 * ok / len(rs):.0f}%)"
        if op == "softdelete":
            silent = [r for r in rs if r["result_changes"]]
            fixed = sum(r["correct"] for r in silent)
            mention = sum(bool(r["mentions_deleted"]) for r in rs)
            summary[op].update({"silent_tasks": len(silent), "silent_fixed": fixed, "mentions_is_deleted": mention})
            line += f"  silent-wrong fixed {fixed}/{len(silent)}, uses is_deleted {mention}/{len(rs)}"
        print(line)
    out_file.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Run a model (or a baseline) on SchemaShift tasks.")
    p.add_argument("task_dir", type=Path, help="folder with tasks.jsonl, changes.json and the variant databases")
    p.add_argument("--model", required=True, help="model name, or the baselines old-query / reference")
    p.add_argument("--mode", choices=("adapt", "question"), default="adapt",
                   help="adapt: give the old query (default); question: give only the question")
    p.add_argument("--hint", action="store_true", help="add the one-line note about the kind of change")
    p.add_argument("--rows", type=int, default=3, help="example rows shown per table")
    p.add_argument("--operators", default=",".join(OPERATORS))
    p.add_argument("--limit", type=int, default=0, help="only the first N tasks (0 = all)")
    p.add_argument("--base-url", default="http://127.0.0.1:11434/v1")  # not "localhost": on Windows it tries IPv6 first
    p.add_argument("--api-key-env", default="", help="name of the environment variable holding the API key")
    p.add_argument("--max-tokens", type=int, default=1024)
    p.add_argument("--timeout", type=int, default=600, help="seconds to wait for one model answer")
    p.add_argument("--out", type=Path, default=Path("results"))
    args = p.parse_args()
    if args.model == "old-query" and args.mode == "question":
        sys.exit("The old-query baseline only makes sense in adapt mode.")

    task_dir = args.task_dir.resolve()
    changes = json.loads((task_dir / "changes.json").read_text(encoding="utf-8"))
    soft_tables = changes["softdelete"]["tables"]
    wanted = args.operators.split(",")
    tasks = [json.loads(line) for line in (task_dir / "tasks.jsonl").open(encoding="utf-8")]
    tasks = [t for t in tasks if t["operator"] in wanted]
    if args.model == "reference":
        tasks = [t for t in tasks if "reference_sql" in t]
    if args.limit:
        tasks = tasks[:args.limit]

    run = run_name(changes["db_id"], args.model, args.mode, args.hint)
    out_file = args.out.resolve() / f"{run}.jsonl"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_file.exists():
        done = {json.loads(line)["task_id"] for line in out_file.open(encoding="utf-8")}
    todo = [t for t in tasks if t["task_id"] not in done]
    print(f"{run}: {len(tasks)} tasks, {len(tasks) - len(todo)} already done, {len(todo)} to run")
    api_key = os.environ.get(args.api_key_env, "") if args.api_key_env else ""

    schemas, schema_dicts = {}, {}
    with out_file.open("a", encoding="utf-8") as f:
        for i, task in enumerate(todo, 1):
            db = task_dir / task["new_db"]
            if db.name not in schemas:
                schemas[db.name] = schema_text(db, args.rows)
                con = open_ro(db)
                schema_dicts[db.name] = load_schema(con)
                con.close()
            start, raw = time.monotonic(), ""
            if args.model == "old-query":
                sql = task["old_sql"]
            elif args.model == "reference":
                sql = task["reference_sql"]
            else:
                prompt = build_prompt(task, schemas[db.name], args.mode, args.hint)
                raw = ask(args.base_url, args.model, api_key, prompt, args.max_tokens, args.timeout)
                sql = extract_sql(raw)
            rows, error = execute(db, sql)
            record = {
                "task_id": task["task_id"], "operator": task["operator"], "question_id": task["question_id"],
                "difficulty": task["difficulty"], "model": args.model, "mode": args.mode, "hint": args.hint,
                "predicted_sql": sql, "error": error,
                "correct": rows is not None and set(rows) == {tuple(r) for r in task["gold_rows"]},
                "seconds": round(time.monotonic() - start, 1),
            }
            if task["operator"] == "softdelete":
                record["result_changes"] = task["result_changes"]
                record["mentions_deleted"] = mentions_deleted(sql, schema_dicts[db.name], soft_tables)
            if raw:
                record["raw"] = raw[:4000]
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            status = "ok" if record["correct"] else ("ERROR" if error else "wrong")
            print(f"[{i}/{len(todo)}] {task['task_id']}: {status} ({record['seconds']}s)")
    summarise(out_file)


if __name__ == "__main__":
    main()
