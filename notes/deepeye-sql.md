# DeepEye-SQL (Li, Chen, Xue, Mei, Luo) — PACMMOD / SIGMOD 2026, doi:10.1145/3802035

## What it is
Text-to-SQL treated like a small software project (SDLC):
1. Requirements — semantic value retrieval (embed TEXT column values, HNSW index) + robust schema linking
   (direct + reversed/"write draft SQL then parse it" + value-based; union; add FK join columns).
2. Implementation — N-version programming: 3 different generators (skeleton, few-shot ICL, divide-and-conquer).
3. Testing — deterministic checker chain (syntax → JOIN/ORDER-BY/time → SELECT/MaxMin/NULL/empty result);
   LLM only fixes what a checker reports.
4. Release — confidence = share of candidates giving the same result; if > 0.6 take it, else LLM pairwise vote.

## Numbers
- BIRD-Dev 73.5% EX, BIRD-Test 75.07%, Spider-Test 89.8%, Spider 2.0-Snow 50.5% (Qwen3-Coder-30B-A3B, no fine-tuning).
- Confidence vs accuracy correlation 0.954 on BIRD-Dev (Fig. 6).
- ~23K input + 23K output tokens, 17.8 s per question; ran on 8x A100 80GB.
- Errors (Fig. 9): schema linking is the biggest category (126) — wrong columns / join paths,
  "triggered by complex multi-hop requirements or obscure column names". ~30% of failures (122) are
  gold-SQL errors or ambiguous questions.

## Links to my study (legacy-style schemas)
- Fig. 4 example: k_symbol = 'SIPO' means "household payment" — a coded value. It was solvable because
  BIRD's evidence hint says so. That hint is a one-line data dictionary. Remove it → my "legacy" condition.
- Value retrieval matches question words to stored values by meaning ('USA' ~ 'United States').
  It cannot link "connected" to 'C' or "deleted" to 'd' — codes carry no meaning to embed.
- Confidence = agreement. Hidden conventions (e.g. a forgotten soft-delete filter) may make ALL candidates
  wrong in the same way → high confidence, wrong answer. Test: does the 0.954 correlation hold on legacy schemas?
- Their checker chain has no checker for application conventions. Idea: a "dictionary checker"
  (e.g. missing soft-delete filter, wrong code value) built from a data dictionary — an SE-style contribution.
- Read next: ref [44] Shkapenyuk et al. 2025, "Automatic Metadata Extraction for Text-to-SQL" (arXiv 2505.19988)
  — closest to building the dictionary automatically.
- DIN-SQL (ref [35]) is Pourreza & Rafiei (U Alberta).
