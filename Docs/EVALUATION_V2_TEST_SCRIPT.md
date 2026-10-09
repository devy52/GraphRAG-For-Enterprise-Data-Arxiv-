# GraphRAG Evaluation V2 — Detailed Verification Test Script

This is an execution-ready verification procedure for the V2 evaluation harness.

**Goal:** prove that the benchmark measures the GraphRAG system rather than artifacts of the evaluator.

---

# 0. Test policy

Do **not** delete the legacy benchmark files.

Do **not** overwrite the previous V2 results during debugging.

During development, write new outputs to:

```text
artifacts/eval_v2_test/
```

Once all tests pass, perform one clean final run into the production result path.

Every failed test must be recorded with:

```text
TEST ID
Observed behavior
Expected behavior
Relevant file/line
Severity
Fix applied
Rerun result
```

---

# 1. Environment and reproducibility

## T001 — Clean project import

From the project root:

### Windows PowerShell

```powershell
python --version
python -m pip --version
python -m compileall src evalharness scripts tests
```

### Expected

- Python is the intended project version.
- `compileall` exits with code 0.

**PASS:** no syntax/import compilation failures.
**FAIL:** any compilation error.

---

## T002 — Install project dependencies

Use the repository's intended installation instructions, then verify the key evaluation stack:

```powershell
python -c "import pydantic; print('pydantic ok')"
python -c "import pytest; print('pytest ok')"
python -c "import openai; print('openai ok')"
```

If RAGAS is part of the intended test environment:

```powershell
python -c "import ragas; print('ragas ok')"
```

**PASS:** all required packages import successfully.
**FAIL:** missing package prevents evaluation tests from collecting.

---

# 2. Run the existing V2 unit tests

## T003 — Text normalization tests

```powershell
pytest -q tests/test_text_norm.py
```

### Must verify

- NFKC normalization works.
- Unicode hyphen variants normalize consistently.
- whitespace normalization works.
- ASCII and Unicode punctuation variants compare equivalently.

---

## T004 — V2 evaluator regression tests

```powershell
pytest -q tests/test_eval_v2.py
```

### Required tests

At minimum, the suite must cover:

1. answerable refusal → fact score 0
2. unanswerable refusal → correctly abstained
3. unanswerable fabricated answer → failure
4. weighted multi-fact scoring
5. Unicode hyphen normalization
6. lexical proxy labeling
7. retrieval metric correctness
8. missing retrieval ground-truth behavior
9. no hardcoded question-ID scoring
10. contradiction handling or an explicitly documented limitation

**PASS:** every intended test executes and passes.
**FAIL:** any missing test or failing test.

---

# 3. Retrieval-ground-truth integrity tests

## T005 — Missing gold IDs must NOT score as perfect retrieval

Create a temporary test case:

```python
from src.eval.evaluator_v2 import EvaluatorV2

e = EvaluatorV2()
r = e.evaluate_retrieval(
    retrieved_chunk_ids=["chunk_a"],
    gold_chunk_ids=[],
)
print(r)
```

### Expected

The result must be clearly marked non-evaluable, e.g.:

```json
{
  "evaluable": false,
  "precision": null,
  "recall": null,
  "mrr": null
}
```

### Forbidden

```json
{"precision": 1.0, "recall": 1.0, "mrr": 1.0}
```

**PASS:** missing labels are N/A.
**FAIL:** missing labels produce perfect retrieval.

---

## T006 — Retrieval formula test

For:

```text
retrieved = [A, B, C]
gold      = [B, D]
```

expected:

```text
hits = {B}
precision = 1/3 = 0.3333
recall    = 1/2 = 0.5000
MRR       = 1/2 = 0.5000
```

Run the evaluator and compare exactly.

---

## T007 — Duplicate retrieval IDs

Test:

```text
retrieved = [A, A, B]
gold = [A]
```

Decide and document whether precision is computed using ranked list entries or unique retrieved documents. The implementation must be consistent and tested.

---

# 4. Dataset integrity tests

## T008 — Every benchmark question has explicit answerability

```powershell
python -c "import json; from pathlib import Path; p=Path('data/benchmark_v2_dataset.jsonl'); rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]; print('questions',len(rows)); assert all(isinstance(r.get('answerable'), bool) for r in rows)"
```

**PASS:** all questions have explicit boolean answerability.

---

## T009 — Every answerable question has required facts

Check:

```text
answerable == true
→ required_facts is non-empty
```

Also check each required fact has:

```text
id
fact
weight > 0
aliases list
```

---

## T010 — Gold retrieval labels are frozen

For every question used for retrieval metrics:

```text
gold_chunk_ids must be explicitly present
```

Do not evaluate retrieval accuracy for a question whose gold IDs are missing.

Export a dataset hash before running:

```powershell
python -c "import hashlib, pathlib; p=pathlib.Path('data/benchmark_v2_dataset.jsonl'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

Store that hash in the benchmark output.

---

# 5. Data-leakage tests

## T011 — Search for gold-answer injection

From project root:

```powershell
rg -n "q\.reference_answer|reference_answer.*text=|text=.*reference_answer" scripts src
```

### Expected

No generation/retrieval path may place `reference_answer` into retrieved context.

A scoring layer may read the gold answer only **after generation**.

**PASS:** no runtime retrieval/generation code injects gold answers.
**FAIL:** any fallback or retrieval object contains the reference answer.

---

## T012 — Gold facts must not reach the judge prompt

Search:

```powershell
rg -n "required_facts|reference_answer|gold_chunk_ids" src/eval scripts
```

Verify that the semantic groundedness judge receives only:

```text
question
retrieved context
generated answer
```

and does not receive:

```text
gold answer
required facts
gold chunk labels
```

---

## T013 — Gold facts must not reach the model generation prompt

Trace the execution path from benchmark runner → router → retrieval → synthesizer.

The prompt sent to the application model must contain retrieved evidence only.

Save one debug prompt for a test question and manually verify that no benchmark gold field is present.

---

# 6. Fact-evaluation tests

## T014 — Full required-fact coverage

Create a question with 3 required facts, equal weights.

Test answer containing all 3.

Expected:

```text
fact_score = 1.0
facts_correct = 3
facts_missing = 0
```

---

## T015 — Partial fact coverage

Three equal-weight required facts; answer contains only two.

Expected:

```text
fact_score = 0.6667
facts_correct = 2
facts_missing = 1
```

---

## T016 — One keyword must NOT make an answer correct

Required facts:

```text
RAG-Sequence
RAG-Token
retriever + generator
```

Answer:

```text
"The system uses a generator for text generation."
```

Expected:

```text
fact_score < 1.0
```

It must not be classified as fully correct.

---

## T017 — Negation/contradiction test

Required fact:

```text
Vladimir Karpukhin is an author.
```

Candidate:

```text
"Vladimir Karpukhin is not an author."
```

Expected behavior:

- The fact must **not** be marked satisfied.
- Preferably classify it as `facts_incorrect = 1`.

If the implementation cannot distinguish this yet, mark the test as a known limitation and do not call the fact metric semantic truth.

---

## T018 — Paraphrase test

Required fact:

```text
DPR uses BERT-base.
```

Candidate:

```text
"The DPR encoders are based on uncased BERT-base."
```

Expected:

- fact should be accepted if using a semantic verifier, or
- the result should be explicitly classified as a lexical-proxy limitation.

---

# 7. Abstention tests

## T019 — Answerable question + refusal

Expected:

```text
fact_score = 0
answerable_incorrect = true
correctly_abstained = false
incorrectly_abstained = true
```

---

## T020 — Unanswerable question + proper refusal

Expected:

```text
fact_score = N/A for factual accuracy aggregation
correctly_abstained = true
incorrectly_abstained = false
```

Do not encode the successful abstention as factual answer correctness.

---

## T021 — Unanswerable question + fabricated answer

Expected:

```text
factual answer success = false
correctly_abstained = false
incorrectly_abstained = true
```

---

## T022 — Remove ambiguous `abstention_correct`

Search:

```powershell
rg -n "abstention_correct" src tests scripts
```

Either remove it or make its semantics literal, e.g.:

```text
did_not_abstain
```

The final benchmark should rely on:

```text
answerable_correct
answerable_incorrect
correctly_abstained
incorrectly_abstained
```

---

# 8. Groundedness tests

## T023 — Label lexical fallback honestly

Run V2 with no judge backend.

The report must say explicitly that groundedness is lexical/heuristic.

Acceptable field name:

```text
lexical_context_overlap_groundedness
```

or an explicit metadata field such as:

```json
{"groundedness_method":"lexical_overlap"}
```

---

## T024 — Semantic judge isolation

When an LLM judge is used, inspect the actual prompt and confirm it contains:

```text
question
retrieved context
answer
```

and not gold answer/facts.

Run a deliberate “poison gold” test by changing the gold answer while leaving context and generated answer unchanged.

Expected:

```text
context_groundedness does not change
```

If it changes, there is data leakage.

---

# 9. Citation/provenance tests

## T025 — Valid vector citation

Citation ID is in retrieved evidence IDs.

Expected:

```text
invalid_citation_reference_rate = 0
```

---

## T026 — Invalid citation

Citation ID is absent from all evidence IDs.

Expected:

```text
invalid_citation_reference_rate > 0
```

---

## T027 — Graph provenance citation

Construct a case where the answer cites a graph-derived provenance chunk that is not in the vector retrieval list but is a valid graph source.

Expected:

- citation is accepted if the graph provenance is part of the canonical evidence universe.

Do not automatically classify it as invalid merely because it is absent from `retrieved_chunk_ids`.

---

# 10. Lexical proxy tests

## T028 — Reference F1 sanity check

For identical strings:

```text
F1 = 1.0
```

For no token overlap:

```text
F1 = 0.0
```

For semantically correct paraphrases:

- record the lexical F1
- do not interpret it as factual accuracy

---

## T029 — Unicode equivalence

These should normalize equivalently:

```text
negative log-likelihood
negative log‑likelihood
negative log–likelihood
negative log—likelihood
```

---

# 11. Stored-result consistency tests

## T030 — Every audit record references a current dataset question

```powershell
python -c "import json; d={json.loads(x)['id'] for x in open('data/benchmark_v2_dataset.jsonl',encoding='utf-8')}; r=[json.loads(x) for x in open('data/benchmark_audit_records_v2.jsonl',encoding='utf-8')]; assert all(x['question_id'] in d for x in r); print('PASS',len(r),'records')"
```

---

## T031 — Recompute retrieval metrics from raw IDs

Never trust stored `retrieval_precision`, `retrieval_recall`, or `retrieval_mrr` alone.

For every record:

```text
retrieved_chunk_ids
        vs.
gold_chunk_ids
```

recompute all three metrics and compare to stored values.

Any mismatch is a benchmark integrity failure.

---

## T032 — Verify dataset/result version identity

Store a SHA-256 hash of:

```text
data/benchmark_v2_dataset.jsonl
```

inside:

```text
benchmark_results_50q_v2.json
benchmark_audit_records_v2.jsonl
```

The run must be reproducible from the exact dataset hash.

---

# 12. Aggregate-metric tests

## T033 — Factual accuracy must exclude unanswerable questions

Compute:

```text
factual_accuracy_answerable_only
```

and separately:

```text
correct_abstention_rate
```

Do not average abstentions into factual correctness.

---

## T034 — Overall success rate

For each question define success as:

```text
(answerable AND answerable_correct)
OR
(not answerable AND correctly_abstained)
```

Then:

```text
overall_success_rate = successes / total_questions
```

Recompute independently from the raw per-question fields.

---

## T035 — Per-hop aggregation

For each tier:

```text
1-hop
2-hop
3-hop
aggregation
out-of-scope
```

recompute:

- fact score
- factual accuracy (answerable-only)
- correct abstention rate
- overall success
- retrieval metrics
- latency

Ensure hop-level averages are weighted by question count, not by arbitrary metric availability.

---

# 13. RAGAS comparison tests

## T036 — Make sample size explicit

The current comparison uses 5 questions.

The report must call it:

> **5-question evaluator comparison / calibration spot check**

not a benchmark.

---

## T037 — Do not call inter-evaluator difference “calibration error”

Replace `MAE`/`calibration` wording with something like:

```text
mean_absolute_inter_evaluator_score_difference
```

unless a trusted reference score exists.

---

## T038 — Handle RAGAS NaN explicitly

A missing RAGAS metric must remain `null`/`NaN` and be excluded from the arithmetic mean for that metric.

Do not convert missing values into zero.

Report:

```text
n_valid_samples
n_missing_samples
mean_over_valid_samples
```

per metric.

---

# 14. Full benchmark execution

## T039 — Freeze the dataset

Once T001–T038 pass:

1. Freeze `benchmark_v2_dataset.jsonl`.
2. Compute SHA-256.
3. Record dataset version/hash.
4. Do not edit the dataset after execution.

---

## T040 — Clean run with separate output directory

Example:

```powershell
python scripts/run_benchmark_v2.py `
  --output-dir artifacts/eval_v2_final `
  --dataset data/benchmark_v2_dataset.jsonl
```

Use the actual CLI arguments exposed by `--help` if names differ.

Run:

```powershell
python scripts/run_benchmark_v2.py --help
```

first.

---

## T041 — Verify execution records

For every question/system:

- answer exists or explicit error state exists
- retrieved evidence is recorded
- no gold answer appears in model context
- latency is present
- dataset hash matches the frozen benchmark

---

# 15. Independent recomputation

## T042 — Independent factual aggregation

Do not use the benchmark's own aggregate code to validate itself.

Write a separate script that reads only:

```text
audit records
benchmark dataset
```

and recomputes:

```text
answerable-only fact score
correctly-abstained count
answerable-correct count
answerable-incorrect count
overall success rate
```

Compare the independent numbers against the reported numbers.

Expected difference:

```text
<= 1e-9
```

or a documented rounding tolerance.

---

## T043 — Independent retrieval recomputation

Similarly recompute:

```text
precision
recall
MRR
```

from raw retrieved/gold IDs.

No dependency on stored summary metrics.

---

# 16. Adversarial benchmark tests

These tests are essential because the benchmark itself must resist gaming.

## T044 — Gold answer changed after generation

Run generation once.

Then alter only the gold reference answer.

Expected:

- model output unchanged
- retrieval unchanged
- groundedness unchanged
- only gold-dependent scoring can change

---

## T045 — Retrieved context changed after generation

Keep answer fixed.

Replace context with unrelated text.

Expected:

- groundedness decreases
- retrieval/evidence metrics can change
- lexical chunk overlap changes

---

## T046 — Correct answer paraphrase

Use two semantically equivalent answers with different wording.

Expected:

- factual semantic score should remain high
- lexical F1 may differ

This test proves the benchmark does not confuse wording with truth.

---

## T047 — One-keyword adversarial answer

Produce an answer that contains exactly one expected keyword but contradicts or omits the required facts.

Expected:

```text
fact_score < 1
```

---

## T048 — Safe refusal adversarial case

Use an answerable question and return:

```text
Insufficient evidence.
```

Expected:

```text
factual answer success = false
correctly_abstained = false
incorrectly_abstained = true
```

But groundedness may reasonably be high because the refusal makes no unsupported factual claim. This is intentional and demonstrates metric separation.

---

# 17. Final pass/fail gates

The benchmark is **FINAL PASS** only if:

### Integrity

- [ ] no gold-answer retrieval fallback
- [ ] no hardcoded question-ID outcomes
- [ ] no missing-gold-as-perfect scoring
- [ ] dataset hash recorded
- [ ] stored results correspond exactly to frozen dataset

### Correctness measurement

- [ ] factual score excludes unanswerable questions
- [ ] abstention correctness is separate
- [ ] contradictions are detected or explicitly documented as unsupported by the metric
- [ ] paraphrase handling is tested
- [ ] one-keyword adversarial answers fail full-correctness scoring

### Groundedness

- [ ] groundedness method explicitly recorded (`LLM` vs `lexical`)
- [ ] judge cannot see gold answer/facts
- [ ] graph provenance is included in valid evidence IDs

### Retrieval

- [ ] every retrieval-evaluable question has gold chunk IDs
- [ ] precision/recall/MRR independently recompute correctly

### Regression

- [ ] all unit tests pass
- [ ] all V2 tests pass
- [ ] RAGAS comparison completes or clearly records unavailable metrics
- [ ] independent aggregate recomputation matches reported results

### Reproducibility

- [ ] model names recorded
- [ ] embedding model recorded
- [ ] judge model recorded
- [ ] dataset hash recorded
- [ ] run timestamp recorded
- [ ] raw per-question evidence preserved

---

# 18. Final report structure

The final benchmark report should contain these separate sections:

```text
1. Retrieval Correctness
2. Factual Answer Correctness (answerable-only)
3. Groundedness
4. Abstention / Answerability
5. Efficiency
6. Lexical Proxy Metrics
7. RAGAS / External Evaluator Comparison
8. Per-question Audit Table
9. Known Limitations
10. Reproducibility Metadata
```

Do **not** publish one headline “accuracy” value unless its exact numerator, denominator, and treatment of abstentions are explicitly defined.
