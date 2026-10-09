# GraphRAG Evaluation Audit — Findings and Required Fixes

**Audit target:** `GraphRAG_Enterprise_Codebase(1).zip`
**Audit date:** 2026-10-03
**Scope:** V2 evaluation refactor, 50-question benchmark, stored V2 results, and Evalkit-vs-RAGAS comparison.

---

## 1. Executive conclusion

The V2 evaluation refactor is a **substantial improvement** over the earlier benchmark. It removes the old single-keyword `matches > 0` shortcut from the V2 factual scorer, adds structured required facts, adds Unicode normalization, separates retrieval/factual/groundedness/abstention/efficiency layers, preserves raw per-question records, and removes the old question-ID hardcoded accuracy overrides from the V2 path.

However, **the current V2 results must not yet be treated as final or publication-grade**. Several methodological and data-integrity issues remain.

The most important findings are:

1. **The stored V2 run is stale relative to the current benchmark dataset.** The dataset now contains populated `gold_chunk_ids`, while the stored V2 result records were produced before those labels were populated. The stored retrieval scores therefore cannot be trusted.
2. **Missing retrieval ground truth is treated as perfect retrieval instead of “not evaluable.”** `evaluate_retrieval()` currently returns recall=1.0 and MRR=1.0 when no gold chunk IDs are present.
3. **The V2 fact scorer is still lexical substring matching.** It is better than `matches > 0`, but it is not true semantic fact verification and cannot reliably detect contradiction or paraphrase.
4. **Unanswerable abstentions are still included as `fact_score=1.0`.** This contaminates the aggregate factual-accuracy number with abstention success. On the current 100 audit records, the all-question score is 0.44 / 0.4067, while answerable-only fact score is approximately 0.30 / 0.2583.
5. **`abstention_correct` is semantically misleading.** It is set to true whenever an answerable question receives a non-refusal answer, even when that answer is wrong. The more meaningful fields are `answerable_correct`, `answerable_incorrect`, `correctly_abstained`, and `incorrectly_abstained`.
6. **V2 groundedness is lexical when no judge backend is provided.** The stored benchmark reports `context_groundedness`, but the runner instantiates `EvaluatorV2()` without a judge. The fallback therefore derives groundedness from lexical overlap rather than an LLM semantic judge.
7. **The benchmark runner contains a gold-answer leakage path.** On retrieval/coordinator failure it inserts `q.reference_answer` into the retrieval context. This violates the V2 zero-data-leakage requirement and must be removed.
8. **Citation validity currently assumes the retrieved chunk-ID list is the complete evidence universe.** In a graph-RAG system, graph-derived provenance can legitimately refer to source chunks that were not present in the vector `retrieved_chunk_ids`. The evaluator should define a unified evidence/provenance ID set before calling a citation invalid.
9. **The RAGAS comparison is useful as evaluator calibration evidence, not ground truth.** It uses only 5 questions. Evalkit and RAGAS diverge materially on some questions, demonstrating that evaluator output is model- and prompt-dependent.
10. **The RAGAS comparison's MAE should be described as inter-evaluator score difference, not calibration error.** There is no trusted ground-truth score against which either evaluator is being calibrated.

---

## 2. What is correctly fixed in V2

### 2.1 Single-keyword accuracy shortcut removed

The V2 factual scorer no longer declares an answer correct simply because one expected keyword appears. It uses weighted required facts and reports:

- `fact_score`
- `facts_correct`
- `facts_missing`
- `facts_incorrect`
- `facts_total`
- `satisfied_fact_ids`
- `missing_fact_ids`

This is a substantial methodological improvement.

### 2.2 Unicode normalization added

`src/eval/text_norm.py` provides centralized normalization, including Unicode NFKC and punctuation/hyphen normalization.

This addresses the earlier false-negative case where an LLM generated a non-breaking hyphen in `negative log‑likelihood` while the expected keyword used ASCII `-`.

### 2.3 Hardcoded question-ID outcomes removed from V2

The V2 code path no longer uses question-specific `is_accurate = False` overrides to manufacture benchmark outcomes.

The old benchmark remains preserved, which is good for auditability.

### 2.4 Layers are explicitly separated

V2 has distinct concepts for:

- retrieval correctness
- factual answer correctness
- context groundedness / unsupported claims
- answerability / abstention
- efficiency
- lexical proxies

This is the correct overall architecture.

### 2.5 Per-question provenance exists

The audit records preserve generated answers, retrieved chunk IDs, retrieved chunk text, citations, latency, model/judge information, and metric outputs. This makes the evaluation inspectable rather than aggregate-only.

---

## 3. Critical issue: stored V2 results do not match the current dataset

The current `data/benchmark_v2_dataset.jsonl` contains populated gold retrieval labels. For example:

```json
"id": "q_1hop_01",
"gold_chunk_ids": ["chunk_arxiv_2004_04906_000"]
```

But the stored audit record for the same question contains retrieved chunk IDs that include that gold chunk, and the stored precision/recall values are `1.0` even for questions whose retrieved set did not match the then-current gold labels.

More importantly, the audit bundle shows that:

- `benchmark_results_50q_v2.json` was written around 15:22
- `benchmark_audit_records_v2.jsonl` was written around 15:22
- `benchmark_v2_dataset.jsonl` was modified later around 22:01

The current dataset therefore reflects a later state than the saved run.

### Consequence

**Do not use the stored retrieval metrics as final V2 evidence. Rerun the benchmark after freezing the final dataset.**

---

## 4. Critical issue: no-gold retrieval must be “N/A”, not perfect

Current behavior in `EvaluatorV2.evaluate_retrieval()` is effectively:

```python
if not gold_chunk_ids:
    return {
        "precision": ...,
        "recall": 1.0,
        "mrr": 1.0,
    }
```

That is methodologically wrong.

When gold retrieval labels are absent, the benchmark has no reference against which retrieval correctness can be measured. The correct result is **not evaluable**.

Recommended representation:

```json
{
  "evaluable": false,
  "precision": null,
  "recall": null,
  "mrr": null
}
```

Do not assign a perfect score merely because the gold labels are missing.

---

## 5. Critical issue: fact scoring is improved but still lexical

The V2 fact scorer checks whether normalized fact text or an alias appears as a substring in the answer:

```python
norm_cand in norm_ans
```

This is better than the previous `matches > 0`, but it remains a **lexical fact-satisfaction proxy**.

### Example false-positive pattern

A fact may be:

> “RAG combines a retriever and a generator.”

An unrelated answer containing the word `generator` can satisfy one alias, even though it does not actually express the required relationship.

### Contradiction problem

An answer such as:

> “DPR was not authored by Vladimir Karpukhin.”

contains the string `Vladimir Karpukhin`, and therefore can satisfy a fact requiring that name unless contradiction detection is added.

### Recommendation

Rename this metric internally/documentationally to something like:

> `weighted_required_fact_lexical_coverage`

unless/ until a semantic fact verifier or blinded human adjudication is added.

A stronger benchmark should eventually distinguish:

- fact explicitly supported
- fact contradicted
- fact absent
- fact semantically paraphrased

---

## 6. Important issue: unanswerable questions contaminate factual accuracy

For an unanswerable question, the V2 scorer currently assigns a correct refusal:

```text
fact_score = 1.0
```

That makes sense as **abstention correctness**, but not as **factual answer correctness**.

The current 50-question records contain 40 answerable questions and 10 out-of-scope questions.

The stored aggregate fact scores are:

| System | All-question fact score | Answerable-only fact score |
|---|---:|---:|
| Plain Vector | 44.00% | 30.00% |
| Hybrid GraphRAG | 40.67% | 25.83% |

Therefore the headline `overall_fact_score` currently mixes two different concepts:

- factual correctness on answerable questions
- successful refusal on unanswerable questions

### Recommended fix

Set factual score to `null` for unanswerable questions and calculate:

```text
factual_accuracy = mean(fact_score for answerable questions only)
```

Keep correctly-abstained as a completely separate metric.

---

## 7. `abstention_correct` is poorly named

The current logic treats a non-refusal answer on an answerable question as `abstention_correct = true`, even if the answer is wrong.

For example:

```text
answerable = true
answer = wrong factual answer
refusal = false
abstention_correct = true
```

That is not abstention correctness.

Use explicit fields instead:

- `answerable_correct`
- `answerable_incorrect`
- `correctly_abstained`
- `incorrectly_abstained`

Prefer removing `abstention_correct` or renaming it to something literal such as `did_not_abstain`.

---

## 8. Important issue: stored V2 groundedness is not an LLM semantic judge

The V2 evaluator supports an LLM judge, but `run_benchmark_v2.py` instantiates:

```python
EvaluatorV2()
```

without a judge backend.

Therefore the groundedness layer falls back to lexical overlap.

This means a stored value such as:

```text
mean_context_groundedness = 0.9805
```

does **not** mean:

> “98.05% of claims were semantically verified as grounded.”

It means the fallback heuristic produced that score.

### Recommendation

Either:

1. provide and explicitly record an LLM judge, or
2. rename the metric to something like:

`lexical_context_overlap_groundedness`

and document it as a heuristic.

Do not present it as semantic groundedness unless a semantic judge actually produced it.

---

## 9. Critical issue: gold-reference leakage in benchmark runner

`run_benchmark_v2.py` contains a retrieval-failure fallback equivalent to:

```python
text=q.reference_answer
```

inside a synthetic retrieval result.

That can put the gold answer directly into the model's context when retrieval/coordinator execution fails.

This violates the benchmark's own zero-data-leakage principle.

### Required behavior

On retrieval failure:

- do not insert the reference answer
- do not manufacture evidence
- record an explicit `error_state`
- either score the run as an execution failure or mark the sample invalid for that run

The gold answer must only be available to the final scoring layer, never to the generation/retrieval path.

---

## 10. Citation metric needs a GraphRAG-specific evidence universe

The current invalid-citation metric compares generated citations against `retrieved_chunk_ids`.

That is insufficient when graph retrieval creates provenance references to source chunks that were not part of the vector retrieval list.

A GraphRAG benchmark should define a canonical evidence universe, for example:

```text
retrieved_vector_chunk_ids
+ graph_source_chunk_ids
+ explicitly attached provenance IDs
= valid_evidence_ids
```

Then a citation is invalid only if it is absent from `valid_evidence_ids`.

Otherwise graph-grounded answers can be falsely penalized.

---

## 11. RAGAS comparison: useful, but not ground truth

The repository includes a genuine Evalkit-vs-RAGAS comparison.

It evaluates **5 questions**, one per tier:

- 1-hop
- 2-hop
- 3-hop
- aggregation
- out-of-scope

This is useful as an evaluator-calibration experiment.

It is **not** a statistically meaningful benchmark and does not prove which evaluator is correct.

### Observed divergences

For the 5-question run, examples include:

| Question | Evalkit faithfulness | RAGAS faithfulness | Interpretation |
|---|---:|---:|---|
| q1 | 0.85 | 0.0 | Large evaluator disagreement |
| q2 | 0.85 | 1.0 | Large evaluator disagreement |
| q3 | 0.85 | N/A/NaN | Missing/failed RAGAS semantic score |

Answer relevancy also diverges substantially on the abstention case.

This demonstrates an important point:

> **LLM-judge scores are evaluator outputs, not ground truth.**

### Terminology correction

The comparison currently calls mean absolute score difference `MAE` and labels it as calibration.

Prefer:

> `mean_absolute_inter_evaluator_score_difference`

There is no trusted true score in this experiment, so it is not calibration error in the statistical sense.

---

## 12. Current V2 aggregate results should be treated as provisional

The stored V2 comparison is:

| Metric | Plain Vector | Hybrid GraphRAG | Delta |
|---|---:|---:|---:|
| Overall fact score | 0.4400 | 0.4067 | -0.0333 |
| Answerable-only fact score | 0.3000 | 0.2583 | -0.0417 |
| Mean groundedness (stored heuristic/judge-free run) | 0.9805 | 0.8478 | -0.1327 |
| Overall success rate | 0.42 | 0.38 | -0.04 |
| Mean latency (ms) | 4241.4 | 16296.3 | +12054.9 |
| Mean reference-text token F1 | 0.3300 | 0.3245 | -0.0055 |
| Lexical chunk overlap | 0.5247 | 0.1829 | -0.3418 |
| Invalid citation reference rate | 0.0000 | 0.1600 | +0.1600 |

These figures are useful diagnostics, but **the retrieval columns must be regenerated after freezing the current dataset**, and factual aggregation should be corrected to exclude unanswerable questions.

The answerable-only values are particularly important: the current all-question fact score overstates factual performance because correct abstentions receive 1.0.

---

## 13. What a trustworthy final benchmark should report

For every question:

```text
question_id
answerable
hop_type
question
reference_answer
required_facts
retrieved_chunk_ids
gold_chunk_ids
retrieval_precision
retrieval_recall
retrieval_mrr
generated_answer
facts_correct
facts_missing
facts_incorrect
fact_score
context_groundedness
unsupported_claim_rate
valid_evidence_ids
citations
invalid_citation_reference_rate
correctly_abstained
incorrectly_abstained
answerable_correct
answerable_incorrect
latency
prompt_tokens
completion_tokens
cost
error_state
```

Then report aggregates separately for:

1. retrieval quality
2. answer factual correctness on answerable questions
3. groundedness
4. abstention quality
5. efficiency
6. lexical proxies

Never collapse these into a single “accuracy” number unless the definition is explicit and justified.

---

## 14. Recommended final acceptance criteria

The V2 benchmark should not be declared final until all of these are true:

- [ ] Final gold retrieval labels are frozen before execution.
- [ ] Stored results are generated from that exact dataset version.
- [ ] Missing retrieval labels return `N/A`, not perfect scores.
- [ ] No reference answer is ever injected into model context.
- [ ] Factual score excludes unanswerable questions.
- [ ] Correct abstention is measured only in the abstention layer.
- [ ] `abstention_correct` is removed or correctly renamed.
- [ ] The factual evaluator detects or otherwise accounts for contradiction.
- [ ] Groundedness is explicitly labeled lexical unless an actual semantic judge runs.
- [ ] Graph provenance is included in the citation evidence universe.
- [ ] RAGAS comparisons use enough questions for the intended claim, or are explicitly called spot/calibration tests.
- [ ] Inter-evaluator score differences are not called ground-truth calibration errors.
- [ ] Full regression tests execute successfully in the project's intended environment.
- [ ] A final per-question audit can reproduce every reported aggregate.

---

## 15. Bottom line

The V2 refactor is **directionally correct and materially better than the old evaluation**.

But the current stored results are **not the final truth about the GraphRAG system** because the evaluation itself still has integrity issues: stale retrieval labels, judge-free lexical groundedness, abstention contamination, lexical fact scoring, and a retrieval-failure gold-answer leakage path.

The correct next step is **not** to tune the GraphRAG system from the existing headline scores. The correct next step is to fix these remaining benchmark issues, run the complete benchmark again, and then audit the regenerated per-question records.
