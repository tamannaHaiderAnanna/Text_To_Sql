# SchemaShift results

| Model | Mode | Hint | Rename | Opaque | Split | Soft-delete | Silent fixed | Uses is_deleted | Tasks |
|---|---|---|---|---|---|---|---|---|---|
| old-query | adapt | no | 0/39 (0%) | 0/39 (0%) | 0/26 (0%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| reference | adapt | no | 39/39 (100%) | 39/39 (100%) | - | - | - | - | 78 |
| qwen2.5-coder:7b | adapt | no | 37/39 (95%) | 8/39 (21%) | 2/26 (8%) | 22/40 (55%) | 0/18 | 0/40 | 144 |
| qwen2.5-coder:7b | adapt | yes | 38/39 (97%) | 11/39 (28%) | 10/26 (38%) | 16/40 (40%) | 5/18 | 40/40 | 144 |

Silent fixed: soft-delete tasks where the old query runs but returns wrong rows, and the model's query returns the right ones.
Uses is_deleted: soft-delete tasks where the model's query reads is_deleted on every soft-deleted table it uses.
