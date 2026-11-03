"""Score every saved run again, more strictly, and add the statistics the pilot needs.

Each saved query is run again on its changed database and compared with the gold answer in
three ways:
  set     the rows as a set: BIRD's rule, and the "correct" that run_models.py stores
  bag     also how often each row appears, so lost or extra duplicate rows count as wrong
  strict  bag, plus the same row order when the old query ends in ORDER BY (used below)
Then, for each run and kind of change: accuracy with a 95% Wilson interval, and the wrong
answers split into SQL errors (loud) and queries that run but return wrong rows (silent).
Two paired tests on the same tasks (exact McNemar, Holm-corrected): with vs without the hint,
and rename vs opaque name. Writes analysis.md, analysis.json and verdicts.jsonl to
<results folder>/analysis/.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\analyse_results.py data\\schemashift\\student_club results
"""
import json
import math
import sqlite3
import statistics
import sys
from collections import Counter
from pathlib import Path

import sqlglot

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off sys.path
from run_models import OPERATORS, execute  # noqa: E402

# Display names, in table order; a model not listed here is shown by its Ollama name, last.
NAMES = {
    "old-query": "Old query unchanged",
    "reference": "Reference rewrite (knows the change)",
    "qwen2.5-coder:1.5b": "Qwen2.5-Coder 1.5B",
    "qwen2.5-coder:3b": "Qwen2.5-Coder 3B",
    "qwen2.5-coder:7b": "Qwen2.5-Coder 7B",
    "qwen2.5-coder:14b": "Qwen2.5-Coder 14B",
    "llama3.1:8b": "Llama 3.1 8B",
    "gemma3:12b": "Gemma 3 12B",
    "phi4:14b": "Phi-4 14B",
    "deepseek-coder-v2:16b": "DeepSeek-Coder-V2 16B",
    "hf.co/mradermacher/OmniSQL-7B-GGUF:Q4_K_M": "OmniSQL 7B",
    "hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M": "Arctic-Text2SQL-R1 7B",
}
BASELINES = ("old-query", "reference")
CHANGE = {"rename": "Rename", "opaque": "Opaque name", "split": "Table split", "softdelete": "Soft-delete"}


def ends_in_order_by(sql: str) -> bool:
    try:
        return bool(sqlglot.parse_one(sql, read="sqlite").args.get("order"))
    except sqlglot.errors.SqlglotError:
        return False


def verdicts(rows, gold: list, ordered: bool) -> dict:
    if rows is None:
        return {"set": False, "bag": False, "strict": False}
    bag = Counter(rows) == Counter(gold)
    return {"set": set(rows) == set(gold), "bag": bag, "strict": bag and (not ordered or rows == gold)}


def same_sql(a: str, b: str) -> bool:
    """The same query text, ignoring spacing, letter case and a final semicolon."""
    def norm(s): return " ".join(s.strip().rstrip(";").split()).lower()
    return norm(a) == norm(b)


def rounded(rows: list) -> list:
    return [tuple(round(x, 6) if isinstance(x, float) else x for x in row) for row in rows]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple:
    """95% Wilson score interval for k successes out of n."""
    if not n:
        return 0.0, 1.0
    p, zz = k / n, z * z
    centre = (p + zz / (2 * n)) / (1 + zz / n)
    half = z * math.sqrt(p * (1 - p) / n + zz / (4 * n * n)) / (1 + zz / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value; b and c count the two kinds of disagreeing pairs."""
    n = b + c
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def holm(pvalues: list) -> list:
    """Holm-Bonferroni adjusted p-values, in the original order."""
    m, running, adjusted = len(pvalues), 0.0, [0.0] * len(pvalues)
    for rank, i in enumerate(sorted(range(m), key=lambda i: pvalues[i])):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def name(model: str) -> str:
    return NAMES.get(model, model)


def model_order(run: dict) -> tuple:
    keys = list(NAMES)
    return keys.index(run["model"]) if run["model"] in keys else len(keys), run["model"], run["mode"], run["hint"]


def score_run(path: Path, tasks: dict, gold: dict, ordered: dict, task_dir: Path) -> dict:
    """Run every saved query of one run again and score it all three ways."""
    records = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    first = records[0]
    run = {"file": path.name, "model": first["model"], "mode": first["mode"], "hint": first["hint"],
           "complete": len(records) == len(tasks), "verdicts": {}}
    for r in records:
        tid = r["task_id"]
        rows, error = execute(task_dir / tasks[tid]["new_db"], r["predicted_sql"])
        v = verdicts(rows, gold[tid], ordered[tid])
        near = rows is not None and not v["strict"] and verdicts(rounded(rows), rounded(gold[tid]), ordered[tid])["strict"]
        v.update(error=error is not None, near=near, stored_correct=r["correct"],
                 stored_error=r["error"] is not None, seconds=r["seconds"],
                 unchanged=same_sql(r["predicted_sql"], tasks[tid]["old_sql"]))
        run["verdicts"][tid] = v
    return run


def per_change(run: dict, tasks: dict, silent: dict) -> dict:
    out = {}
    for op in OPERATORS:
        vs = [(tid, v) for tid, v in run["verdicts"].items() if tasks[tid]["operator"] == op]
        if not vs:
            continue
        k, n = sum(v["strict"] for _, v in vs), len(vs)
        lo, hi = wilson(k, n)
        s = {"tasks": n, "correct_set": sum(v["set"] for _, v in vs), "correct_bag": sum(v["bag"] for _, v in vs),
             "correct": k, "ci95": [round(lo, 3), round(hi, 3)], "sql_error": sum(v["error"] for _, v in vs),
             "ran_but_wrong": sum(not v["error"] and not v["strict"] for _, v in vs),
             "old_query_unchanged": sum(v["unchanged"] for _, v in vs)}
        if op == "softdelete":
            hidden = [v for tid, v in vs if silent[tid]]
            s.update(silent_tasks=len(hidden), silent_fixed=sum(v["strict"] for v in hidden))
        out[op] = s
    return out


def paired(a: dict, b: dict, pairs: list) -> dict:
    """Compare two sets of verdicts on the same pairs of tasks: (task in a, task in b)."""
    only_a = sum(a[x]["strict"] and not b[y]["strict"] for x, y in pairs)
    only_b = sum(b[y]["strict"] and not a[x]["strict"] for x, y in pairs)
    return {"pairs": len(pairs), "correct_a": sum(a[x]["strict"] for x, _ in pairs),
            "correct_b": sum(b[y]["strict"] for _, y in pairs), "only_a": only_a, "only_b": only_b,
            "p": mcnemar(only_a, only_b)}


def cell(s: dict) -> str:
    k, n = s["correct"], s["tasks"]
    lo, hi = s["ci95"]
    return f"{k}/{n} {100 * k / n:.0f}% ({100 * lo:.0f}–{100 * hi:.0f})"


def p_text(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def table(header: list, rows: list) -> list:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + \
           ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: analyse_results.py <task folder> <results folder>")
    task_dir, results = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    tasks = {t["task_id"]: t for t in map(json.loads, (task_dir / "tasks.jsonl").open(encoding="utf-8"))}
    gold = {tid: [tuple(r) for r in t["gold_rows"]] for tid, t in tasks.items()}
    ordered = {tid: ends_in_order_by(t["old_sql"]) for tid, t in tasks.items()}
    # silent tasks: the old query still runs on the changed database but returns other rows
    silent = {}
    for tid, t in tasks.items():
        rows, error = execute(task_dir / t["new_db"], t["old_sql"])
        silent[tid] = error is None and not verdicts(rows, gold[tid], ordered[tid])["strict"]

    runs = [score_run(p, tasks, gold, ordered, task_dir) for p in sorted(results.glob("*.jsonl"))
            if p.name != "run_log.jsonl" and p.stat().st_size > 0]
    runs.sort(key=model_order)
    complete = [r for r in runs if r["complete"]]
    for r in runs:
        r["by_change"] = per_change(r, tasks, silent)
        r["median_seconds"] = statistics.median(v["seconds"] for v in r["verdicts"].values())
    models = [r for r in complete if r["model"] not in BASELINES]

    # 1. does re-running reproduce the stored verdicts?
    rerun = [(r["file"], tid) for r in runs for tid, v in r["verdicts"].items()
             if v["set"] != v["stored_correct"] or v["error"] != v["stored_error"]]
    total = sum(len(r["verdicts"]) for r in runs)

    # 2. hint vs no hint, and rename vs opaque, on the same tasks
    hint_tests = []
    for r in models:
        if r["hint"]:
            continue
        twin = next((h for h in models if h["model"] == r["model"] and h["mode"] == r["mode"] and h["hint"]), None)
        if twin is None:
            continue
        for op in OPERATORS + ("softdelete-silent",):
            ids = [tid for tid, t in tasks.items() if t["operator"] == op.split("-")[0]
                   and (op != "softdelete-silent" or silent[tid])]
            hint_tests.append({"model": r["model"], "change": op, **paired(r["verdicts"], twin["verdicts"],
                                                                           [(i, i) for i in ids])})
    for t, p in zip(hint_tests, holm([t["p"] for t in hint_tests])):
        t["p_holm"] = p
    pairs = [(f"{t['db_id']}-{t['question_id']}-rename", f"{t['db_id']}-{t['question_id']}-opaque")
             for t in tasks.values() if t["operator"] == "rename"]
    pairs = [(a, b) for a, b in pairs if b in tasks]
    name_tests = [{"model": r["model"], "hint": r["hint"], **paired(r["verdicts"], r["verdicts"], pairs)}
                  for r in models]
    for t, p in zip(name_tests, holm([t["p"] for t in name_tests])):
        t["p_holm"] = p

    # 3. loud or silent: how the wrong answers fail, for the models run both with and without the hint
    both = {r["model"] for r in models if r["hint"]} & {r["model"] for r in models if not r["hint"]}
    loud = []
    for op in OPERATORS:
        for hint in (False, True):
            s = [r["by_change"][op] for r in models if r["model"] in both and r["hint"] == hint and op in r["by_change"]]
            wrong = sum(x["tasks"] - x["correct"] for x in s)
            loud.append({"change": op, "hint": hint, "runs": len(s), "answers": sum(x["tasks"] for x in s),
                         "wrong": wrong, "sql_error": sum(x["sql_error"] for x in s),
                         "ran_but_wrong": sum(x["ran_but_wrong"] for x in s),
                         "old_query_unchanged": sum(x["old_query_unchanged"] for x in s)})

    # 4. where the three scoring rules disagree
    disagree = Counter()
    for r in complete:
        for tid, v in r["verdicts"].items():
            if v["set"] != v["strict"]:
                disagree[(tid, "duplicate rows" if not v["bag"] else "row order")] += 1
    near = sum(v["near"] for r in complete for v in r["verdicts"].values())
    multi_row_ordered = sum(ordered[tid] and len(gold[tid]) > 1 for tid in tasks)
    with_duplicates = sum(len(set(gold[tid])) < len(gold[tid]) for tid in tasks)
    soft_ids = [tid for tid, t in tasks.items() if t["operator"] == "softdelete"]
    silent_count = sum(silent[tid] for tid in soft_ids)
    silent_set = sum(tasks[tid]["result_changes"] for tid in soft_ids)

    # --- write the report
    out = results / "analysis"
    out.mkdir(exist_ok=True)
    md = ["# SchemaShift: strict scores and statistics", "",
          f"Made by `scripts/analyse_results.py` from {len(runs)} result files ({len(complete)} complete), "
          f"re-run on SQLite {sqlite3.sqlite_version}.", "",
          "**Scoring.** Every saved query was run again on its changed database. *Strict* (used in all "
          "tables) means the same rows the same number of times, and in the same order when the old "
          "query ends in ORDER BY. *BIRD set* compares the rows as a set, ignoring duplicates and order; "
          "it is what `run_models.py` stores as `correct`. Intervals are 95% Wilson intervals. Paired "
          "tests are exact McNemar tests on the same tasks, Holm-corrected within each table.", "",
          "## 1. Accuracy by kind of change (strict)", ""]
    rows = []
    for r in complete:
        bc = r["by_change"]
        sd = bc.get("softdelete", {})
        rows.append([name(r["model"]), "yes" if r["hint"] else "no", *(cell(bc[op]) for op in OPERATORS),
                     f"{sd.get('silent_fixed', 0)}/{sd.get('silent_tasks', 0)}", f"{r['median_seconds']:.1f}"])
    md += table(["Model", "Hint", *(CHANGE[op] for op in OPERATORS), "Silent soft-delete fixed",
                 "Median s/task"], rows)
    incomplete = [f"{name(r['model'])}{' + hint' if r['hint'] else ''} ({len(r['verdicts'])}/{len(tasks)} tasks)"
                  for r in runs if not r["complete"]]
    md += ["", f"Each cell: correct/tasks, percent, (95% interval). Silent soft-delete tasks are the "
               f"{silent_count} soft-delete tasks where the old query still runs but returns wrong rows "
               f"(BIRD's set rule finds {silent_set})."]
    if incomplete:
        md += ["", "Left out because they are incomplete: " + "; ".join(incomplete) + "."]

    left_out = sorted({name(r["model"]) for r in models if r["model"] not in both})
    md += ["", "## 2. Loud or silent: how wrong answers fail", "",
           f"All wrong answers of the {len(both)} models run both without and with the hint"
           + (f" (left out: {', '.join(left_out)})" if left_out else "") + ". *SQL error*: the query does "
           "not run (loud). *Ran, wrong rows*: it runs and returns a wrong result (silent).", ""]
    rows = []
    for x in loud:
        share = f"{100 * x['ran_but_wrong'] / x['wrong']:.0f}%" if x["wrong"] else "–"
        rows.append([CHANGE[x["change"]], "yes" if x["hint"] else "no", x["answers"], x["wrong"],
                     x["sql_error"], x["ran_but_wrong"], share])
    md += table(["Change", "Hint", "Answers", "Wrong", "SQL error", "Ran, wrong rows", "Silent share of wrong"], rows)
    kept = {x["hint"]: x for x in loud if x["change"] == "softdelete"}
    if kept:
        md += ["", "Soft-delete answers that are the old query unchanged (ignoring spacing and case): "
                   + "; ".join(f"{'with' if h else 'without'} the hint {x['old_query_unchanged']} of {x['answers']}"
                               for h, x in sorted(kept.items())) + "."]

    md += ["", "## 3. Does the hint help? Same model, same tasks", ""]
    rows = [[name(t["model"]), CHANGE.get(t["change"], "Soft-delete, silent tasks only"),
             f"{t['correct_a']}/{t['pairs']}", f"{t['correct_b']}/{t['pairs']}", t["only_a"], t["only_b"],
             p_text(t["p"]), p_text(t["p_holm"])] for t in hint_tests]
    md += table(["Model", "Change", "No hint", "Hint", "Only no-hint right", "Only hint right", "p", "Holm p"], rows)

    md += ["", "## 4. Rename vs opaque name: same questions, same six columns", ""]
    rows = [[name(t["model"]), "yes" if t["hint"] else "no", f"{t['correct_a']}/{t['pairs']}",
             f"{t['correct_b']}/{t['pairs']}", t["only_a"], t["only_b"], p_text(t["p"]), p_text(t["p_holm"])]
            for t in name_tests]
    md += table(["Model", "Hint", "Rename", "Opaque name", "Only rename right", "Only opaque right", "p",
                 "Holm p"], rows)

    md += ["", "## 5. Checks", "",
           f"- Re-running the {total} saved queries reproduced the stored verdict and error status for "
           f"{total - len(rerun)}" + (f"; differences: {', '.join(f'{f} {t}' for f, t in rerun)}." if rerun else "."),
           f"- {multi_row_ordered} tasks end in ORDER BY and return more than one row; "
           f"{with_duplicates} have duplicate rows in the gold answer.",
           f"- Strict and BIRD-set verdicts differ in {sum(disagree.values())} of "
           f"{sum(len(r['verdicts']) for r in complete)} answers:"]
    md += [f"  - `{tid}`: {why}, {n} run{'s' if n > 1 else ''}" for (tid, why), n in sorted(disagree.items())]
    md += [f"- Answers that fail only because of floating-point noise (equal after rounding to 6 decimals): {near}."]
    (out / "analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    summary = {"sqlite_version": sqlite3.sqlite_version, "silent_tasks": silent_count, "silent_tasks_set_rule": silent_set,
               "rerun_differences": rerun, "set_vs_strict": [{"task_id": t, "reason": w, "runs": n}
                                                             for (t, w), n in sorted(disagree.items())],
               "float_noise_only": near,
               "runs": [{k: r[k] for k in ("file", "model", "mode", "hint", "complete", "median_seconds", "by_change")}
                        for r in runs],
               "loud_or_silent": loud, "hint_tests": hint_tests, "rename_vs_opaque": name_tests}
    (out / "analysis.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out / "verdicts.jsonl").open("w", encoding="utf-8") as f:
        for r in runs:
            for tid, v in r["verdicts"].items():
                f.write(json.dumps({"file": r["file"], "task_id": tid, **{k: v[k] for k in (
                    "set", "bag", "strict", "error", "stored_correct")}}) + "\n")
    print(f"{len(runs)} runs, {total} answers re-run, {len(rerun)} differ from the stored verdict; "
          f"silent soft-delete tasks: {silent_count} strict, {silent_set} set rule")
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
