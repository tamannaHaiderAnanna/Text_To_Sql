"""Compare every run in a results folder: one row per run, one column per kind of change.

Reads the results/<db>__<model>__<mode>[__hint].jsonl files written by run_models.py,
prints a table and writes it to <results folder>/comparison.md.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\compare_results.py results
"""
import json
import sys
from pathlib import Path

OPERATORS = ("rename", "opaque", "split", "softdelete")
BASELINES = ("old-query", "reference")


def score(path: Path) -> dict:
    """Correct/total per kind of change, plus the two soft-delete checks."""
    records = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    first = records[0]
    row = {"model": first["model"], "mode": first["mode"], "hint": first["hint"], "tasks": len(records)}
    for op in OPERATORS:
        rs = [r for r in records if r["operator"] == op]
        row[op] = (sum(r["correct"] for r in rs), len(rs))
    soft = [r for r in records if r["operator"] == "softdelete"]
    silent = [r for r in soft if r["result_changes"]]
    row["silent"] = (sum(r["correct"] for r in silent), len(silent))
    row["is_deleted"] = (sum(bool(r["mentions_deleted"]) for r in soft), len(soft))
    return row


def cell(pair: tuple, percent: bool = True) -> str:
    ok, n = pair
    if not n:
        return "-"
    return f"{ok}/{n} ({100 * ok / n:.0f}%)" if percent else f"{ok}/{n}"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: compare_results.py <results folder>")
    folder = Path(sys.argv[1])
    rows = [score(p) for p in sorted(folder.glob("*.jsonl"))
            if p.name != "run_log.jsonl" and p.stat().st_size > 0]
    # baselines first, then models by name, each without hint before with hint
    rows.sort(key=lambda r: (r["model"] not in BASELINES, r["model"], r["mode"], r["hint"]))

    header = ["Model", "Mode", "Hint", "Rename", "Opaque", "Split", "Soft-delete",
              "Silent fixed", "Uses is_deleted", "Tasks"]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        lines.append("| " + " | ".join([
            r["model"], r["mode"], "yes" if r["hint"] else "no",
            *(cell(r[op]) for op in OPERATORS),
            cell(r["silent"], percent=False), cell(r["is_deleted"], percent=False), str(r["tasks"]),
        ]) + " |")
    table = "\n".join(lines)
    print(table)
    notes = ("\n\nScored with BIRD's set rule, as stored by run_models.py. Strict scores, 95% intervals and "
             "paired tests are in analysis/analysis.md (scripts/analyse_results.py).\n"
             "Silent fixed: soft-delete tasks where the old query runs but returns wrong rows, "
             "and the model's query returns the right ones.\n"
             "Uses is_deleted: soft-delete tasks where the model's query reads is_deleted on every "
             "soft-deleted table it uses.\n")
    (folder / "comparison.md").write_text("# SchemaShift results\n\n" + table + notes, encoding="utf-8")
    print(f"\nWritten to {folder / 'comparison.md'}")


if __name__ == "__main__":
    main()
