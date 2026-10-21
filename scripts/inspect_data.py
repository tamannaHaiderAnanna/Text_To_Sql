"""Quick look at BIRD Mini-Dev: counts, databases, one sample question, one test query.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\inspect_data.py data\\bird_minidev
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


def find_one(root: Path, name: str) -> Path:
    hits = sorted(root.rglob(name))
    if not hits:
        sys.exit(f"Could not find {name} under {root}")
    return hits[0]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: inspect_data.py <path-to-unzipped-minidev>")
    root = Path(sys.argv[1]).resolve()

    questions_file = find_one(root, "mini_dev_sqlite.json")
    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    print(f"Questions file : {questions_file}")
    print(f"Questions      : {len(questions)}")
    print(f"Fields         : {sorted(questions[0].keys())}")

    print("\nQuestions per database:")
    for db, n in Counter(q["db_id"] for q in questions).most_common():
        print(f"  {db:<28} {n}")

    if "difficulty" in questions[0]:
        print("\nDifficulty:", dict(Counter(q["difficulty"] for q in questions)))

    db_files = {p.stem: p for p in root.rglob("*.sqlite")}
    print(f"\nSQLite databases found: {len(db_files)}")
    for name, path in sorted(db_files.items()):
        print(f"  {name:<28} {path.stat().st_size / 1_048_576:8.1f} MB")

    sample = questions[0]
    print("\nSample question")
    print("  db       :", sample["db_id"])
    print("  question :", sample["question"])
    print("  evidence :", sample.get("evidence", ""))
    print("  gold SQL :", sample["SQL"])

    db_path = db_files.get(sample["db_id"])
    if db_path is None:
        sys.exit(f"No .sqlite file for {sample['db_id']}")
    # Read-only connection, so the original database is never modified.
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    rows = con.execute(sample["SQL"]).fetchmany(5)
    con.close()
    print("  result   :", rows)


if __name__ == "__main__":
    main()
