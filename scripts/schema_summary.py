"""Summarise a SQLite database: tables, columns, and the values of small categorical columns.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\schema_summary.py <db.sqlite> [<db.sqlite> ...]
"""
import sqlite3
import sys
from pathlib import Path

MAX_DISTINCT = 8  # treat a text column as "categorical" when it has this many values or fewer


def summarise(db_path: Path) -> None:
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    print(f"\n=== {db_path.stem}: {len(tables)} tables ===")
    for table in tables:
        cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        rows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"\n{table} ({rows} rows)")
        for _, name, col_type, *_ in cols:
            line = f"  {name:<28} {col_type or ''}"
            if (col_type or "").upper() in ("TEXT", ""):
                values = con.execute(
                    f'SELECT DISTINCT "{name}" FROM "{table}" WHERE "{name}" IS NOT NULL LIMIT {MAX_DISTINCT + 1}'
                ).fetchall()
                if 0 < len(values) <= MAX_DISTINCT:
                    line += "  values: " + ", ".join(repr(v[0]) for v in values)
            print(line)
    con.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: schema_summary.py <db.sqlite> [<db.sqlite> ...]")
    for arg in sys.argv[1:]:
        summarise(Path(arg).resolve())
