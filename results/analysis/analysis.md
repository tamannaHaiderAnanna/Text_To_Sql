# SchemaShift: strict scores and statistics

Made by `scripts/analyse_results.py` from 21 result files (19 complete), re-run on SQLite 3.50.4.

**Scoring.** Every saved query was run again on its changed database. *Strict* (used in all tables) means the same rows the same number of times, and in the same order when the old query ends in ORDER BY. *BIRD set* compares the rows as a set, ignoring duplicates and order; it is what `run_models.py` stores as `correct`. Intervals are 95% Wilson intervals. Paired tests are exact McNemar tests on the same tasks, Holm-corrected within each table.

## 1. Accuracy by kind of change (strict)

| Model | Hint | Rename | Opaque name | Table split | Soft-delete | Silent soft-delete fixed | Median s/task |
|---|---|---|---|---|---|---|---|
| Old query unchanged | no | 0/39 0% (0–9) | 0/39 0% (0–9) | 0/26 0% (0–13) | 22/40 55% (40–69) | 0/18 | 0.0 |
| Reference rewrite (knows the change) | no | 39/39 100% (91–100) | 39/39 100% (91–100) | 26/26 100% (87–100) | 40/40 100% (91–100) | 18/18 | 0.0 |
| Qwen2.5-Coder 1.5B | no | 9/39 23% (13–38) | 2/39 5% (1–17) | 1/26 4% (1–19) | 22/40 55% (40–69) | 0/18 | 0.5 |
| Qwen2.5-Coder 1.5B | yes | 12/39 31% (19–46) | 5/39 13% (6–27) | 2/26 8% (2–24) | 25/40 62% (47–76) | 11/18 | 0.6 |
| Qwen2.5-Coder 7B | no | 37/39 95% (83–99) | 8/39 21% (11–36) | 2/26 8% (2–24) | 22/40 55% (40–69) | 0/18 | 2.2 |
| Qwen2.5-Coder 7B | yes | 38/39 97% (87–100) | 11/39 28% (16–44) | 10/26 38% (22–57) | 16/40 40% (26–55) | 5/18 | 2.8 |
| Qwen2.5-Coder 14B | no | 39/39 100% (91–100) | 31/39 79% (64–89) | 17/26 65% (46–81) | 24/40 60% (45–74) | 2/18 | 4.6 |
| Qwen2.5-Coder 14B | yes | 39/39 100% (91–100) | 39/39 100% (91–100) | 22/26 85% (66–94) | 35/40 88% (74–94) | 14/18 | 5.0 |
| Llama 3.1 8B | no | 25/39 64% (48–77) | 10/39 26% (15–41) | 7/26 27% (14–46) | 18/40 45% (31–60) | 4/18 | 2.8 |
| Llama 3.1 8B | yes | 26/39 67% (51–79) | 17/39 44% (29–59) | 8/26 31% (16–50) | 27/40 68% (52–80) | 12/18 | 2.8 |
| Gemma 3 12B | no | 36/39 92% (80–97) | 16/39 41% (27–57) | 9/26 35% (19–54) | 21/40 52% (38–67) | 0/18 | 7.5 |
| Gemma 3 12B | yes | 36/39 92% (80–97) | 15/39 38% (25–54) | 11/26 42% (26–61) | 35/40 88% (74–94) | 15/18 | 8.2 |
| Phi-4 14B | no | 38/39 97% (87–100) | 25/39 64% (48–77) | 20/26 77% (58–89) | 22/40 55% (40–69) | 1/18 | 10.6 |
| DeepSeek-Coder-V2 16B | no | 36/39 92% (80–97) | 4/39 10% (4–24) | 9/26 35% (19–54) | 21/40 52% (38–67) | 0/18 | 2.9 |
| DeepSeek-Coder-V2 16B | yes | 38/39 97% (87–100) | 3/39 8% (3–20) | 9/26 35% (19–54) | 31/40 78% (62–88) | 14/18 | 3.0 |
| OmniSQL 7B | no | 35/39 90% (76–96) | 11/39 28% (16–44) | 4/26 15% (6–34) | 22/40 55% (40–69) | 0/18 | 18.3 |
| OmniSQL 7B | yes | 36/39 92% (80–97) | 15/39 38% (25–54) | 7/26 27% (14–46) | 22/40 55% (40–69) | 0/18 | 18.1 |
| Arctic-Text2SQL-R1 7B | no | 37/39 95% (83–99) | 20/39 51% (36–66) | 19/26 73% (54–86) | 22/40 55% (40–69) | 0/18 | 20.3 |
| Arctic-Text2SQL-R1 7B | yes | 38/39 97% (87–100) | 25/39 64% (48–77) | 22/26 85% (66–94) | 24/40 60% (45–74) | 2/18 | 19.7 |

Each cell: correct/tasks, percent, (95% interval). Silent soft-delete tasks are the 18 soft-delete tasks where the old query still runs but returns wrong rows (BIRD's set rule finds 18).

Left out because they are incomplete: Qwen2.5-Coder 3B (57/144 tasks); Qwen2.5-Coder 3B + hint (57/144 tasks).

## 2. Loud or silent: how wrong answers fail

All wrong answers of the 8 models run both without and with the hint (left out: Phi-4 14B). *SQL error*: the query does not run (loud). *Ran, wrong rows*: it runs and returns a wrong result (silent).

| Change | Hint | Answers | Wrong | SQL error | Ran, wrong rows | Silent share of wrong |
|---|---|---|---|---|---|---|
| Rename | no | 312 | 58 | 37 | 21 | 36% |
| Rename | yes | 312 | 49 | 30 | 19 | 39% |
| Opaque name | no | 312 | 210 | 127 | 83 | 40% |
| Opaque name | yes | 312 | 182 | 101 | 81 | 45% |
| Table split | no | 208 | 140 | 131 | 9 | 6% |
| Table split | yes | 208 | 117 | 104 | 13 | 11% |
| Soft-delete | no | 320 | 148 | 2 | 146 | 99% |
| Soft-delete | yes | 320 | 105 | 55 | 50 | 48% |

Soft-delete answers that are the old query unchanged (ignoring spacing and case): without the hint 240 of 320; with the hint 56 of 320.

## 3. Does the hint help? Same model, same tasks

| Model | Change | No hint | Hint | Only no-hint right | Only hint right | p | Holm p |
|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder 1.5B | Rename | 9/39 | 12/39 | 0 | 3 | 0.250 | 1.000 |
| Qwen2.5-Coder 1.5B | Opaque name | 2/39 | 5/39 | 0 | 3 | 0.250 | 1.000 |
| Qwen2.5-Coder 1.5B | Table split | 1/26 | 2/26 | 0 | 1 | 1.000 | 1.000 |
| Qwen2.5-Coder 1.5B | Soft-delete | 22/40 | 25/40 | 8 | 11 | 0.648 | 1.000 |
| Qwen2.5-Coder 1.5B | Soft-delete, silent tasks only | 0/18 | 11/18 | 0 | 11 | <0.001 | 0.036 |
| Qwen2.5-Coder 7B | Rename | 37/39 | 38/39 | 0 | 1 | 1.000 | 1.000 |
| Qwen2.5-Coder 7B | Opaque name | 8/39 | 11/39 | 0 | 3 | 0.250 | 1.000 |
| Qwen2.5-Coder 7B | Table split | 2/26 | 10/26 | 0 | 8 | 0.008 | 0.266 |
| Qwen2.5-Coder 7B | Soft-delete | 22/40 | 16/40 | 11 | 5 | 0.210 | 1.000 |
| Qwen2.5-Coder 7B | Soft-delete, silent tasks only | 0/18 | 5/18 | 0 | 5 | 0.062 | 1.000 |
| Qwen2.5-Coder 14B | Rename | 39/39 | 39/39 | 0 | 0 | 1.000 | 1.000 |
| Qwen2.5-Coder 14B | Opaque name | 31/39 | 39/39 | 0 | 8 | 0.008 | 0.266 |
| Qwen2.5-Coder 14B | Table split | 17/26 | 22/26 | 0 | 5 | 0.062 | 1.000 |
| Qwen2.5-Coder 14B | Soft-delete | 24/40 | 35/40 | 1 | 12 | 0.003 | 0.120 |
| Qwen2.5-Coder 14B | Soft-delete, silent tasks only | 2/18 | 14/18 | 0 | 12 | <0.001 | 0.019 |
| Llama 3.1 8B | Rename | 25/39 | 26/39 | 0 | 1 | 1.000 | 1.000 |
| Llama 3.1 8B | Opaque name | 10/39 | 17/39 | 1 | 8 | 0.039 | 1.000 |
| Llama 3.1 8B | Table split | 7/26 | 8/26 | 1 | 2 | 1.000 | 1.000 |
| Llama 3.1 8B | Soft-delete | 18/40 | 27/40 | 2 | 11 | 0.022 | 0.696 |
| Llama 3.1 8B | Soft-delete, silent tasks only | 4/18 | 12/18 | 0 | 8 | 0.008 | 0.266 |
| Gemma 3 12B | Rename | 36/39 | 36/39 | 0 | 0 | 1.000 | 1.000 |
| Gemma 3 12B | Opaque name | 16/39 | 15/39 | 3 | 2 | 1.000 | 1.000 |
| Gemma 3 12B | Table split | 9/26 | 11/26 | 1 | 3 | 0.625 | 1.000 |
| Gemma 3 12B | Soft-delete | 21/40 | 35/40 | 2 | 16 | 0.001 | 0.047 |
| Gemma 3 12B | Soft-delete, silent tasks only | 0/18 | 15/18 | 0 | 15 | <0.001 | 0.002 |
| DeepSeek-Coder-V2 16B | Rename | 36/39 | 38/39 | 0 | 2 | 0.500 | 1.000 |
| DeepSeek-Coder-V2 16B | Opaque name | 4/39 | 3/39 | 2 | 1 | 1.000 | 1.000 |
| DeepSeek-Coder-V2 16B | Table split | 9/26 | 9/26 | 2 | 2 | 1.000 | 1.000 |
| DeepSeek-Coder-V2 16B | Soft-delete | 21/40 | 31/40 | 5 | 15 | 0.041 | 1.000 |
| DeepSeek-Coder-V2 16B | Soft-delete, silent tasks only | 0/18 | 14/18 | 0 | 14 | <0.001 | 0.005 |
| OmniSQL 7B | Rename | 35/39 | 36/39 | 2 | 3 | 1.000 | 1.000 |
| OmniSQL 7B | Opaque name | 11/39 | 15/39 | 4 | 8 | 0.388 | 1.000 |
| OmniSQL 7B | Table split | 4/26 | 7/26 | 1 | 4 | 0.375 | 1.000 |
| OmniSQL 7B | Soft-delete | 22/40 | 22/40 | 0 | 0 | 1.000 | 1.000 |
| OmniSQL 7B | Soft-delete, silent tasks only | 0/18 | 0/18 | 0 | 0 | 1.000 | 1.000 |
| Arctic-Text2SQL-R1 7B | Rename | 37/39 | 38/39 | 0 | 1 | 1.000 | 1.000 |
| Arctic-Text2SQL-R1 7B | Opaque name | 20/39 | 25/39 | 0 | 5 | 0.062 | 1.000 |
| Arctic-Text2SQL-R1 7B | Table split | 19/26 | 22/26 | 0 | 3 | 0.250 | 1.000 |
| Arctic-Text2SQL-R1 7B | Soft-delete | 22/40 | 24/40 | 0 | 2 | 0.500 | 1.000 |
| Arctic-Text2SQL-R1 7B | Soft-delete, silent tasks only | 0/18 | 2/18 | 0 | 2 | 0.500 | 1.000 |

## 4. Rename vs opaque name: same questions, same six columns

| Model | Hint | Rename | Opaque name | Only rename right | Only opaque right | p | Holm p |
|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder 1.5B | no | 9/39 | 2/39 | 7 | 0 | 0.016 | 0.062 |
| Qwen2.5-Coder 1.5B | yes | 12/39 | 5/39 | 7 | 0 | 0.016 | 0.062 |
| Qwen2.5-Coder 7B | no | 37/39 | 8/39 | 29 | 0 | <0.001 | <0.001 |
| Qwen2.5-Coder 7B | yes | 38/39 | 11/39 | 27 | 0 | <0.001 | <0.001 |
| Qwen2.5-Coder 14B | no | 39/39 | 31/39 | 8 | 0 | 0.008 | 0.039 |
| Qwen2.5-Coder 14B | yes | 39/39 | 39/39 | 0 | 0 | 1.000 | 1.000 |
| Llama 3.1 8B | no | 25/39 | 10/39 | 16 | 1 | <0.001 | 0.002 |
| Llama 3.1 8B | yes | 26/39 | 17/39 | 11 | 2 | 0.022 | 0.062 |
| Gemma 3 12B | no | 36/39 | 16/39 | 20 | 0 | <0.001 | <0.001 |
| Gemma 3 12B | yes | 36/39 | 15/39 | 23 | 2 | <0.001 | <0.001 |
| Phi-4 14B | no | 38/39 | 25/39 | 14 | 1 | <0.001 | 0.006 |
| DeepSeek-Coder-V2 16B | no | 36/39 | 4/39 | 32 | 0 | <0.001 | <0.001 |
| DeepSeek-Coder-V2 16B | yes | 38/39 | 3/39 | 35 | 0 | <0.001 | <0.001 |
| OmniSQL 7B | no | 35/39 | 11/39 | 24 | 0 | <0.001 | <0.001 |
| OmniSQL 7B | yes | 36/39 | 15/39 | 22 | 1 | <0.001 | <0.001 |
| Arctic-Text2SQL-R1 7B | no | 37/39 | 20/39 | 17 | 0 | <0.001 | <0.001 |
| Arctic-Text2SQL-R1 7B | yes | 38/39 | 25/39 | 13 | 0 | <0.001 | 0.002 |

## 5. Checks

- Re-running the 2850 saved queries reproduced the stored verdict and error status for 2850.
- 3 tasks end in ORDER BY and return more than one row; 14 have duplicate rows in the gold answer.
- Strict and BIRD-set verdicts differ in 15 of 2736 answers:
  - `student_club-1322-rename`: duplicate rows, 1 run
  - `student_club-1334-split`: duplicate rows, 1 run
  - `student_club-1338-opaque`: duplicate rows, 9 runs
  - `student_club-1387-rename`: duplicate rows, 1 run
  - `student_club-1399-opaque`: duplicate rows, 1 run
  - `student_club-1435-rename`: duplicate rows, 2 runs
- Answers that fail only because of floating-point noise (equal after rounding to 6 decimals): 0.
