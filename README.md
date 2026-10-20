# Text-to-SQL on Legacy-Style Schemas

**Question:** When a database hides the meaning of its data — generic column names
(`Attribute1`…`AttributeN`), coded values (`'a'`, `'c'`, `'d'`), and soft-delete flags —
how much does AI-generated SQL accuracy drop, does the AI notice when it is wrong,
and does a data dictionary bring the accuracy back?

## Plan

| Version | What the AI sees |
|---|---|
| 1. Clean | The original database (BIRD Mini-Dev) |
| 2. Legacy | Same data, with generic column names, coded values and soft-deleted rows |
| 3. Legacy + dictionary | Version 2 plus a short dictionary of what each column and code means |
| 4. Legacy + code (later) | Version 2 plus small application code that uses the columns |

Metric: **execution accuracy** — run the AI's SQL and the correct SQL; same result = correct.

## Folder layout

- `data/` — BIRD Mini-Dev and the generated legacy copies (not committed to Git)
- `scripts/` — Python scripts
- `results/` — result tables
- `notes/` — reading notes and drafts

## Setup

```
.venv\Scripts\activate
pip install -r requirements.txt
```

Data: [BIRD Mini-Dev](https://github.com/bird-bench/mini_dev) — public benchmark (no company data is used).
