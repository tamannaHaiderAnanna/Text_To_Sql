# SchemaShift: can LLMs fix an existing SQL query after the database schema changes?

Databases change: columns get renamed, tables are split, a "deleted" flag is added. Every
query written for the old schema then breaks or, worse, keeps running and silently returns
wrong rows. Developers now ask AI assistants to update such queries. This project measures
how reliably open LLMs do that, and which kinds of change they cannot handle.

The model gets only the **new schema** (with three example rows per table) and the **old
query**. It is never told what changed. Its rewritten query is run on the changed database
and compared with a gold answer that is computed automatically.

## The four kinds of change

Built from the 48 gold queries of BIRD Mini-Dev's `student_club` database, giving 144 tasks.

| Change | What is done to the database | Tasks |
|---|---|---|
| Rename | 6 columns get natural new names (`first_name` → `given_name`) | 39 |
| Opaque name | The same 6 columns become `Attribute1`, `Attribute2`, … | 39 |
| Table split | Columns move to a new table that shares the primary key (`member` → `member_contact`) | 26 |
| Soft-delete | `member` and `event` get `is_deleted`; 30% of their rows are marked deleted | 40 |

How the gold answer is found without hand-labelling:

- **Rename, opaque name, table split** keep all the data, so the gold answer is the old query's result on the original database.
- **Soft-delete:** the gold answer is the old query's result on a copy where the marked rows are really deleted. In 18 of the 40 tasks the old query still runs but returns wrong rows; these **silent errors** are the real test, because leaving the query unchanged already matches the other 22.

Each model runs twice: **without a hint**, and **with a one-line hint** that names the kind of change but not the column (for example *"Rows with is_deleted = 1 have been deleted and must be ignored."*).

## Pilot results

Nine open models on a Colab T4 GPU (Ollama 0.40.8–0.40.11, 4-bit Q4_K_M, temperature 0, one run each, 22–25 October 2026). Each cell is **without hint → with hint**.

| Model | Rename | Opaque name | Table split | Soft-delete: silent errors fixed |
|---|---|---|---|---|
| Qwen2.5-Coder 1.5B | 23% → 31% | 5% → 13% | 4% → 8% | 0/18 → 11/18 |
| Qwen2.5-Coder 7B | 95% → 97% | 21% → 28% | 8% → 38% | 0/18 → 5/18 |
| Qwen2.5-Coder 14B | 100% → 100% | 79% → 100% | 65% → 85% | 2/18 → 14/18 |
| Llama 3.1 8B | 64% → 67% | 31% → 46% | 27% → 35% | 4/18 → 12/18 |
| Gemma 3 12B | 95% → 95% | 44% → 41% | 35% → 42% | 0/18 → 15/18 |
| Phi-4 14B | 97% → – | 67% → – | 77% → – | 1/18 → – |
| DeepSeek-Coder-V2 16B | 92% → 97% | 10% → 8% | 35% → 35% | 0/18 → 14/18 |
| OmniSQL 7B (SQL-specialised) | 92% → 95% | 31% → 41% | 15% → 27% | 0/18 → 0/18 |
| Arctic-Text2SQL-R1 7B (SQL-specialised, reasons first) | 95% → 97% | 54% → 67% | 73% → 85% | 0/18 → 2/18 |
| Baseline: old query unchanged | 0% | 0% | 0% | 0/18 |

What stands out:

- **Natural renames are easy; meaningless names are not.** With the same six columns, DeepSeek-Coder-V2 drops from 92% to 10% and Qwen 7B from 95% to 21%.
- **Without a hint, no model noticed the soft-delete rule:** at most 4 of the 18 silent errors were fixed.
- **The hint helps large general models a lot** (Gemma 3 12B: 0 → 15 of 18) **but SQL-specialised models mostly ignore it** (OmniSQL: 0 → 0).
- **A hint can also hurt:** with it, Qwen 7B added `is_deleted` to tables that do not have the column, and its soft-delete accuracy fell from 22/40 to 16/40.
- **Errors are almost all of one kind:** 593 of the 594 SQL errors are "no such column", that is, a stale or invented column name.

Incomplete runs: Qwen2.5-Coder 3B stopped at task 58 of 144 (a script bug, now fixed), and Phi-4's hint run did not finish (the server crashed). Both will be rerun.

## How to reproduce

All commands run from the project folder. On Windows the virtual environment's Python is `.venv\Scripts\python.exe`.

1. Set up Python 3.13 and the one dependency:
   ```
   python -m venv .venv
   .venv\Scripts\activate          (Linux/macOS: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
2. Download [BIRD Mini-Dev](https://github.com/bird-bench/mini_dev) and unpack it to `data/bird_minidev/` (about 1.4 GB, not committed).
3. Build the four changed databases and the 144 tasks:
   ```
   python -I scripts/make_schema_changes.py data/bird_minidev/minidev/MINIDEV student_club data/schemashift
   ```
4. Check the scoring with the two baselines, which need no model (`reference` should score 100%):
   ```
   python -I scripts/run_models.py data/schemashift/student_club --model old-query
   python -I scripts/run_models.py data/schemashift/student_club --model reference
   ```
5. Run models. With Ollama on a GPU machine:
   ```
   python -I scripts/run_models.py data/schemashift/student_club --model qwen2.5-coder:7b
   python -I scripts/run_models.py data/schemashift/student_club --model qwen2.5-coder:7b --hint
   ```
   Or on Google Colab: pack the files with `scripts/make_colab_zip.py`, open `notebooks/colab_run_models.ipynb`, and upload the zip when asked. The notebook runs a list of models, skips finished runs, and can continue in a later session.
6. Compare every run: `python -I scripts/compare_results.py results` (writes `results/comparison.md`).

`-I` keeps Python from importing code from the current folder, a precaution when working next to downloaded data.

## Repository layout

| Path | Contents |
|---|---|
| `scripts/make_schema_changes.py` | Builds the changed databases, the gold answers and `tasks.jsonl`, and checks its own work |
| `scripts/run_models.py` | Sends each task to any OpenAI-compatible endpoint (Ollama, vLLM, a hosted API), runs the returned SQL read-only, and scores it |
| `scripts/compare_results.py` | One table row per run, written to `results/comparison.md` |
| `scripts/make_colab_zip.py` | Packs scripts, task data and results so far for Colab |
| `scripts/inspect_data.py`, `schema_summary.py`, `count_hidden_meaning.py` | Early exploration of BIRD Mini-Dev (see below) |
| `notebooks/colab_run_models.ipynb` | Runs many models on a free Colab GPU |
| `results/` | One file per run: `<db>__<model>__<mode>[__hint].jsonl`, one line per task (the SQL the model wrote, any error, whether it was correct, and for soft-delete tasks whether it uses `is_deleted`), plus a `.summary.json`, `run_log.jsonl` and `comparison.md` |
| `notes/` | Reading notes |
| `data/` | BIRD Mini-Dev and the generated databases (not committed; rebuilt by step 3) |

## Earlier exploration

The project started from a related question: how well do LLMs cope with legacy-style
schemas, where column names and coded values hide their meaning? A first count on BIRD's
`financial` database (`scripts/count_hidden_meaning.py`) found that 29 of its 32 gold queries
need a hidden meaning, and that BIRD's "evidence" hint gives that meaning away in 28 of them.
SchemaShift's opaque-name and soft-delete changes come from this question.

## Related work

- [EvoSchema](https://arxiv.org/abs/2603.10697) (VLDB 2025) tests text-to-SQL under schema changes, but the model writes SQL from the question, never from the old query.
- [Migrator](https://arxiv.org/abs/1904.05498) (PLDI 2019) rewrites database programs after schema refactoring with program synthesis and a proof of equivalence, without LLMs.
- [BIRD](https://arxiv.org/abs/2305.03111) (NeurIPS 2023) is the benchmark the tasks are built from.

## Next steps

- Finish the incomplete runs and add reasoning models (Qwen3 8B, DeepSeek-R1 8B).
- Compare with the "write it again from the question" setting used by EvoSchema.
- Add a second database (`financial`) and label the mistakes by hand to build a taxonomy.
- Build and test a simple check that catches silent soft-delete errors.

## Data and license

The code is released under the [MIT License](LICENSE).

[BIRD Mini-Dev](https://github.com/bird-bench/mini_dev) is released under CC BY-SA 4.0. The
changed databases are derived from it and are not stored here; `scripts/make_schema_changes.py`
rebuilds them. No company or private data is used.

Author: Tamanna Haider
