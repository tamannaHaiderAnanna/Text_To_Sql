"""Count questions in one BIRD database whose correct SQL depends on generic columns or coded values,
and check whether the evidence hint explains them.

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\count_hidden_meaning.py <mini_dev_sqlite.json> financial
"""
import json
import re
import sys
from pathlib import Path

# Hidden-meaning patterns in BIRD's "financial" database.
GENERIC_COLUMN = re.compile(r"\bA\d{1,2}\b")  # district.A2 ... A16
CODED_VALUES = [
    "'A'", "'B'", "'C'", "'D'",                         # loan.status
    "PRIJEM", "VYDAJ", "VYBER",                         # trans.type / operation
    "VKLAD", "PREVOD",                                  # trans.operation
    "SIPO", "UVER", "POJISTNE", "LEASING", "SLUZBY", "DUCHOD", "UROK", "SANKC",  # k_symbol
    "POPLATEK",                                         # account.frequency
    "OWNER", "DISPONENT",                               # disp.type
]
SHOW = 3  # examples to print per group


def mentioned(item: str, text: str) -> bool:
    """True when the hint names the column or code. A one-letter code must appear quoted,
    otherwise every capital letter in the hint would count."""
    bare = item.strip("'")
    if len(bare) == 1:
        return f"'{bare}'" in text or f'"{bare}"' in text
    return re.search(rf"\b{re.escape(bare)}\b", text) is not None


def show(title: str, questions: list) -> None:
    print(f"\n{title}")
    for q in questions[:SHOW]:
        print(f"  [{q['question_id']}] {q['question']}")
        print(f"      hint: {q.get('evidence') or '(none)'}")
        print(f"      SQL : {q['SQL'][:160]}")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: count_hidden_meaning.py <mini_dev_sqlite.json> <db_id>")
    questions = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    db_id = sys.argv[2]
    subset = [q for q in questions if q["db_id"] == db_id]

    generic = coded = 0
    explained, unexplained = [], []
    for q in subset:
        sql = q["SQL"]
        columns = GENERIC_COLUMN.findall(sql)
        codes = [c for c in CODED_VALUES if c in sql]
        generic += bool(columns)
        coded += bool(codes)
        if columns or codes:
            evidence = q.get("evidence", "")
            if any(mentioned(item, evidence) for item in columns + codes):
                explained.append(q)
            else:
                unexplained.append(q)

    print(f"Database                         : {db_id}")
    print(f"Questions                        : {len(subset)}")
    print(f"Use generic columns (A2..A16)    : {generic}")
    print(f"Use coded values                 : {coded}")
    print(f"Use either (hidden meaning)      : {len(explained) + len(unexplained)}")
    print(f"...whose evidence hint names them: {len(explained)}")
    show("Examples where the hint gives the meaning away:", explained)
    show("Examples where the hint does not name it:", unexplained)


if __name__ == "__main__":
    main()
