# SchemaShift results

| Model | Mode | Hint | Rename | Opaque | Split | Soft-delete | Silent fixed | Uses is_deleted | Tasks |
|---|---|---|---|---|---|---|---|---|---|
| old-query | adapt | no | 0/39 (0%) | 0/39 (0%) | 0/26 (0%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| reference | adapt | no | 39/39 (100%) | 39/39 (100%) | 26/26 (100%) | 40/40 (100%) | 18/18 | 40/40 | 144 |
| deepseek-coder-v2:16b | adapt | no | 36/39 (92%) | 4/39 (10%) | 9/26 (35%) | 21/40 (52%) | 0/18 | 1/40 | 144 |
| deepseek-coder-v2:16b | adapt | yes | 38/39 (97%) | 3/39 (8%) | 9/26 (35%) | 31/40 (78%) | 14/18 | 35/40 | 144 |
| gemma3:12b | adapt | no | 37/39 (95%) | 17/39 (44%) | 9/26 (35%) | 21/40 (52%) | 0/18 | 0/40 | 144 |
| gemma3:12b | adapt | yes | 37/39 (95%) | 16/39 (41%) | 11/26 (42%) | 35/40 (88%) | 15/18 | 38/40 | 144 |
| hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M | adapt | no | 37/39 (95%) | 21/39 (54%) | 19/26 (73%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q4_K_M | adapt | yes | 38/39 (97%) | 26/39 (67%) | 22/26 (85%) | 24/40 (60%) | 2/18 | 5/40 | 144 |
| hf.co/mradermacher/OmniSQL-7B-GGUF:Q4_K_M | adapt | no | 36/39 (92%) | 12/39 (31%) | 4/26 (15%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| hf.co/mradermacher/OmniSQL-7B-GGUF:Q4_K_M | adapt | yes | 37/39 (95%) | 16/39 (41%) | 7/26 (27%) | 22/40 (55%) | 0/18 | 1/40 | 144 |
| llama3.1:8b | adapt | no | 25/39 (64%) | 12/39 (31%) | 7/26 (27%) | 18/40 (45%) | 4/18 | 2/40 | 144 |
| llama3.1:8b | adapt | yes | 26/39 (67%) | 18/39 (46%) | 9/26 (35%) | 27/40 (68%) | 12/18 | 31/40 | 144 |
| phi4:14b | adapt | no | 38/39 (97%) | 26/39 (67%) | 20/26 (77%) | 22/40 (55%) | 1/18 | 2/40 | 144 |
| qwen2.5-coder:1.5b | adapt | no | 9/39 (23%) | 2/39 (5%) | 1/26 (4%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| qwen2.5-coder:1.5b | adapt | yes | 12/39 (31%) | 5/39 (13%) | 2/26 (8%) | 25/40 (62%) | 11/18 | 22/40 | 144 |
| qwen2.5-coder:14b | adapt | no | 39/39 (100%) | 31/39 (79%) | 17/26 (65%) | 24/40 (60%) | 2/18 | 5/40 | 144 |
| qwen2.5-coder:14b | adapt | yes | 39/39 (100%) | 39/39 (100%) | 22/26 (85%) | 35/40 (88%) | 14/18 | 40/40 | 144 |
| qwen2.5-coder:3b | adapt | no | 9/16 (56%) | 1/16 (6%) | 0/9 (0%) | 9/16 (56%) | 0/7 | 0/16 | 57 |
| qwen2.5-coder:3b | adapt | yes | 10/16 (62%) | 3/16 (19%) | 1/9 (11%) | 13/16 (81%) | 5/7 | 14/16 | 57 |
| qwen2.5-coder:7b | adapt | no | 37/39 (95%) | 8/39 (21%) | 2/26 (8%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| qwen2.5-coder:7b | adapt | yes | 38/39 (97%) | 11/39 (28%) | 10/26 (38%) | 16/40 (40%) | 5/18 | 40/40 | 144 |

Scored with BIRD's set rule, as stored by run_models.py. Strict scores, 95% intervals and paired tests are in analysis/analysis.md (scripts/analyse_results.py).
Silent fixed: soft-delete tasks where the old query runs but returns wrong rows, and the model's query returns the right ones.
Uses is_deleted: soft-delete tasks where the model's query reads is_deleted on every soft-deleted table it uses.
