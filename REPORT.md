# SchemaShift: can open LLMs repair a SQL query after the schema changes?

**Preliminary report, November 2026** · Tamanna Haider

This is a pilot on one database. The numbers are early results, not final findings.

## Summary

When a database schema changes, a query written for the old schema either fails with an
error (a *loud* failure) or keeps running and returns wrong rows (a *silent* failure).
Developers increasingly ask LLMs to update such queries. I built 144 repair tasks from the
BIRD Mini-Dev benchmark and tested nine open models from 1.5B to 16B parameters.

- **Meaningless names are much harder than new names.** Seven of the nine models repair
  90–100% of the queries after six columns get natural new names. When the same six columns
  get generic names such as `Attribute1`, they repair only 10–79%.
- **Many wrong repairs are silent.** Without a hint, 99% of the wrong answers after a
  soft-delete change run without error and return wrong rows. So do 40% of the wrong answers
  after the opaque renames. Wrong answers after a table split are almost always SQL errors.
- **A one-line hint helps some models and not others.** Told that rows with
  `is_deleted = 1` must be ignored, Gemma 3 12B fixes 15 of 18 silent errors (none without
  the hint). The text-to-SQL model OmniSQL 7B still fixes none.

## 1. Task

The model receives two things: the new schema (CREATE TABLE statements and three example
rows per table) and the old query. It must return a query that gives the same result on the
new database, and it is not told what changed. Its query runs on the changed database
(read-only SQLite, 10-second limit) and is compared with a gold answer.

## 2. Benchmark

The source is the `student_club` database of BIRD Mini-Dev (CC BY-SA 4.0) and its 48 gold
queries; 44 of them use a part of the database that changes. A script applies four changes,
each to its own copy:

| Change | What the script does | Tasks |
|---|---|---|
| Rename | Six columns get natural new names (`first_name` → `given_name`) | 39 |
| Opaque name | The same six columns become `Attribute1`, `Attribute2`, … | 39 |
| Table split | Columns move to a new table that shares the primary key (`member` → `member_contact`) | 26 |
| Soft delete | `member` and `event` get an `is_deleted` column; 30% of their rows are marked deleted | 40 |

Gold answers need no hand labelling:
- **Rename, opaque name and table split** keep all the data, so the gold answer is the old
  query's result on the original database.
- **Soft delete:** the gold answer is the old query's result on a copy where the marked rows
  are really deleted. In 18 of these 40 tasks the unchanged query still runs but returns
  wrong rows.

Every task also has a reference rewrite made by a fixed rule that knows the change: rename
the columns, join the new table on the key, or skip deleted rows. All 144 return exactly the
gold rows. So every task can be solved, and with a change log the problem is easy. The
models get no change log and must work out the change from the new schema.

The 144 tasks are 44 questions crossed with the changes each one touches, all on one
database, so they are not independent observations.

## 3. Setup

- **Models:**
  - Qwen2.5-Coder 1.5B, 7B and 14B;
  - Llama 3.1 8B;
  - Gemma 3 12B;
  - Phi-4 14B;
  - DeepSeek-Coder-V2 16B;
  - two text-to-SQL models, OmniSQL 7B and Arctic-Text2SQL-R1 7B.

  All run in Ollama on a free Colab T4 GPU, at temperature 0, once per setting. All are
  4-bit: Q4_K_M, except Q4_0 for DeepSeek-Coder-V2.
- **Two settings:** no hint, and a one-line hint that names the kind of change but not the
  columns. An example hint: *"Some columns were renamed to generic names such as Attribute1."*
- **Scoring:** an answer is correct only if it returns the same rows, the same number of
  times, in the same order when the query ends in ORDER BY. BIRD's usual comparison treats
  the rows as a set. That rule would have accepted 15 wrong answers here, 12 of them with a
  wrong filter or join (for example `type = 'Meeting'` in place of the renamed event-name
  column).
- **Statistics:** 95% Wilson intervals; exact McNemar tests on paired tasks, Holm-corrected
  within each family of tests.

## 4. Results

Strict accuracy, **without hint → with hint**:

| Model | Rename | Opaque name | Table split | Silent soft-delete errors fixed |
|---|---|---|---|---|
| Qwen2.5-Coder 1.5B | 23% → 31% | 5% → 13% | 4% → 8% | 0/18 → 11/18 |
| Qwen2.5-Coder 7B | 95% → 97% | 21% → 28% | 8% → 38% | 0/18 → 5/18 |
| Qwen2.5-Coder 14B | 100% → 100% | 79% → 100% | 65% → 85% | 2/18 → 14/18 |
| Llama 3.1 8B | 64% → 67% | 26% → 44% | 27% → 31% | 4/18 → 12/18 |
| Gemma 3 12B | 92% → 92% | 41% → 38% | 35% → 42% | 0/18 → 15/18 |
| Phi-4 14B | 97% → – | 64% → – | 77% → – | 1/18 → – |
| DeepSeek-Coder-V2 16B | 92% → 97% | 10% → 8% | 35% → 35% | 0/18 → 14/18 |
| OmniSQL 7B | 90% → 92% | 28% → 38% | 15% → 27% | 0/18 → 0/18 |
| Arctic-Text2SQL-R1 7B | 95% → 97% | 51% → 64% | 73% → 85% | 0/18 → 2/18 |
| Old query unchanged | 0% | 0% | 0% | 0/18 |
| Rule that knows the change | 100% | 100% | 100% | 18/18 |

With 26–40 tasks per cell the intervals are wide: 21% on 39 tasks means 11–36%. All
intervals and tests are in [results/analysis/analysis.md](results/analysis/analysis.md).
Phi-4 has no run with the hint.

**Natural and meaningless names.** The rename and opaque-name tasks use the same questions
and the same six columns; only the new names differ. The drop from rename to opaque name is
significant in 13 of 17 runs, and large: DeepSeek-Coder-V2 16B falls from 92% to 10%, and
Qwen2.5-Coder 7B from 95% to 21%.

**Loud and silent failures.** This table covers the eight models run in both settings,
without the hint:

| Change | Wrong answers | SQL error (loud) | Ran, wrong rows (silent) |
|---|---|---|---|
| Rename | 58 | 37 | 21 (36%) |
| Opaque name | 210 | 127 | 83 (40%) |
| Table split | 140 | 131 | 9 (6%) |
| Soft delete | 148 | 2 | 146 (99%) |

The silent failures have two sources:
- **Soft delete:** the old query is still valid SQL. Models mostly return it unchanged (240
  of 320 answers), so they inherit its error.
- **Opaque renames:** models often swap in an existing column whose name looks right, such as
  `department` for the renamed `major_name`, or `type` for the renamed `event_name`. The
  query runs, and the result is wrong.

The loud failures are nearly all of one kind: 593 of the 594 SQL errors across all runs are
"no such column". Feeding that error back to the model is the natural next condition. It
cannot help with silent failures, which produce no error.

**The hint.** On the 18 silent soft-delete tasks, the hint brings significant gains for four
of eight models:
- Gemma 3 12B: 0 → 15;
- DeepSeek-Coder-V2: 0 → 14;
- Qwen2.5-Coder 14B: 2 → 14;
- Qwen2.5-Coder 1.5B: 0 → 11.

The two text-to-SQL models hardly use it: OmniSQL 0 → 0, Arctic 0 → 2.

The hint also changes how models fail. Soft-delete SQL errors rise from 2 to 55, all of them
`is_deleted` used on a table that does not have it. Qwen2.5-Coder 7B's soft-delete score
falls from 22 to 16 of 40, though this drop is not significant (p = 0.21). On rename,
opaque-name and table-split tasks, no effect of the hint survives the correction for
multiple tests. The largest gain there is Qwen2.5-Coder 7B on table splits, 8% → 38%
(p = 0.008 before correction).

**Size and reasoning.**
- Within one family (Qwen2.5-Coder 1.5B → 7B → 14B):
  - opaque-name accuracy rises from 5% to 21% to 79%;
  - table-split accuracy rises from 4% to 8% to 65%;
  - without the hint, none of the three notices the soft delete (0, 0 and 2 of 18 fixed).
- Arctic-Text2SQL-R1 7B, which reasons before answering, solves 73% of the table splits,
  against 8% for Qwen2.5-Coder 7B. It takes about 20 seconds per task instead of 2.

## 5. Limitations

- **Small sample.** One database and 44 questions. Tasks built from the same question are
  correlated.
- **No held-out test set yet.** The prompt and hints were written while looking at these
  tasks.
- **Single runs.** Each setting ran once with 4-bit models, so run-to-run variation is
  unmeasured. Exact model digests were not recorded. Qwen2.5-Coder 3B and Phi-4's hint run
  are incomplete.
- **Narrow change set.** Four kinds of change, all repairable. No task tests whether a
  model recognises a change that cannot be repaired.
- **Possible contamination.** BIRD is public, so models may have seen the original queries
  during training.
- **Scoring on one database.** Returning the gold rows on one database does not prove that
  two queries are equivalent.

## 6. Next steps

1. **Execution feedback.** Return the SQLite error and allow a second attempt. Compare schema
   information and feedback in a 2×2 design. This should mainly help the loud failures.
2. **More databases and kinds of change.**
   - Add more BIRD Mini-Dev databases, with a held-out test set split by database.
   - Add a type change. For example, a cost stored in cents also fails silently.
   - Add column removal, and changes that cannot be repaired.
3. **Reliability.** Repeat runs, finish the incomplete ones, and label the failures by hand
   to build a taxonomy.
4. **Catching silent errors.** Test simple checks that flag a likely silent failure before
   the query is used.

## Reproducing

The code, the task builder and every model output are in this repository; the
[README](README.md) gives the steps. Every number in this report comes from the saved
outputs, via `python -I scripts/analyse_results.py data/schemashift/student_club results`.
