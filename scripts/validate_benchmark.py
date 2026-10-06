# -*- coding: utf-8 -*-
"""
Benchmark Validation Harness — independent audit of evalkit benchmark scores.

Architecture Role:
    Standalone audit tool in scripts/. Does NOT modify src/ or evalkit. It answers
    "how correct are the reported benchmark scores?" with evidence that does not
    depend on trusting the original run:

      1. Deterministic recompute  — re-derive token-F1 / exact-match from the stored
         outputs with an independent implementation and diff against stored scores.
      2. Paired run comparison    — baseline vs optimized per-question deltas with a
         seeded bootstrap 95% CI, plus the subset of questions that the change under
         test (vector-route retrieval filtering) can actually affect.
      3. Objective outcomes       — judge-free correctness: abstention detection,
         expected-keyword recall, and whether the answer exists in the pgvector corpus.
      4. Judge repeatability      — re-score the same (question, answer, context) K times
         with the same judge at temperature 0, logging RAW responses and detecting the
         production judge's silent fallbacks (0.5 default / loose-regex number grab).
      5. Judge cross-check        — score with a second, independent judge model and
         report correlation and per-question disagreement.

Inputs:
    - baseline / optimized `full_eval_results.json` (from scripts/run_full_evaluation.py)
    - data/evalkit_dataset.jsonl, live FastAPI server (http://127.0.0.1:8000), pgvector
    - .env (LLM_BASE_URL, LLM_API_KEY, EXTRACTION_MODEL) — keys are never printed.

Outputs (in --output-dir):
    - validation_results.json   raw machine-readable evidence (incl. raw judge replies)
    - validation_report.md      human-readable audit report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT / "evalkit", _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from evalkit.evaluators.rag import (  # noqa: E402
    _ANSWER_RELEVANCY_PROMPT,
    _CONTEXT_PRECISION_PROMPT,
    _FAITHFULNESS_PROMPT,
)
from evalkit.evaluators.retrieval import _lexical_overlap  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (no magic numbers)
# ---------------------------------------------------------------------------
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 7
CI_LOWER_PCT = 2.5
CI_UPPER_PCT = 97.5
JUDGE_REPEATS = 3
JUDGE_WORKERS = 2  # kept low: the NIM gateway returns HTTP 429 under higher concurrency
JUDGE_BACKOFF_S = (5, 15, 30, 60, 90)  # waits between retries on HTTP 429 rate limits
JUDGE_TIMEOUT_S = 120.0
CHUNK_UTIL_THRESHOLD = 0.15  # mirrors evalkit RetrievalEvaluator default
KEYWORD_CORRECT_RECALL = 0.5  # >= this fraction of expected keywords => "correct"
DEFAULT_ALT_JUDGE = "meta/llama-3.3-70b-instruct"
DEFAULT_API_URL = "http://127.0.0.1:8000/query"
JUDGE_JSON_SUFFIX = (
    "\n\nReturn ONLY a JSON object with this exact shape: "
    '{"score": 0.85, "reasoning": "brief justification"}. '
    "The score must be a number from 0.0 to 1.0."
)
STORED_JUDGE_METRICS = [
    "rag.faithfulness",
    "rag.hallucination_rate",
    "rag.context_precision",
    "rag.answer_relevancy",
    "retrieval.chunk_utilization",
    "text_similarity.f1",
]
ABSTAIN_RE = re.compile(
    r"(does not (contain|specify|provide|include)|insufficient (evidence|information)|"
    r"lacks? sufficient evidence|no information|cannot (be )?(answer|determine)|not (enough|sufficient))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 1. Deterministic recompute
# ---------------------------------------------------------------------------
def _tokens(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def independent_f1(output: str, reference: str) -> float:
    """SQuAD-style token F1 re-implemented with collections.Counter (differs from evalkit's loops)."""
    out_c, ref_c = Counter(_tokens(output)), Counter(_tokens(reference))
    if not out_c or not ref_c:
        return 1.0 if out_c == ref_c else 0.0
    overlap = sum((out_c & ref_c).values())
    if overlap == 0:
        return 0.0
    p = overlap / sum(out_c.values())
    r = overlap / sum(ref_c.values())
    return 2 * p * r / (p + r)


def load_results(path: Path) -> Dict[str, Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {ex["metadata"]["id"]: ex for ex in data["per_example"]}


def check_deterministic(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    rows, max_f1_diff, em_mismatch = [], 0.0, 0
    for qid, ex in results.items():
        stored_f1 = ex["scores"].get("text_similarity.f1")
        stored_em = ex["scores"].get("text_similarity.exact_match")
        new_f1 = independent_f1(ex["adapter_output"], ex["reference"])
        new_em = 1.0 if ex["adapter_output"].strip() == ex["reference"].strip() else 0.0
        diff = abs(new_f1 - stored_f1) if stored_f1 is not None else float("nan")
        max_f1_diff = max(max_f1_diff, diff) if diff == diff else max_f1_diff
        em_mismatch += int(stored_em is not None and new_em != stored_em)
        rows.append({"id": qid, "stored_f1": stored_f1, "recomputed_f1": new_f1, "abs_diff": diff})
    return {"rows": rows, "max_abs_f1_diff": max_f1_diff, "em_mismatches": em_mismatch}


# ---------------------------------------------------------------------------
# 2. Paired comparison with bootstrap CI
# ---------------------------------------------------------------------------
def bootstrap_ci(deltas: List[float]) -> Tuple[float, float, float]:
    if not deltas:
        return (float("nan"),) * 3
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(deltas)
    means = sorted(
        statistics.fmean(rng.choices(deltas, k=n)) for _ in range(BOOTSTRAP_RESAMPLES)
    )
    lo = means[int(BOOTSTRAP_RESAMPLES * CI_LOWER_PCT / 100)]
    hi = means[int(BOOTSTRAP_RESAMPLES * CI_UPPER_PCT / 100) - 1]
    return statistics.fmean(deltas), lo, hi


def paired_comparison(
    base: Dict[str, Dict[str, Any]], opt: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    ids = sorted(set(base) & set(opt))
    vector_ids = [
        i for i in ids if opt[i]["adapter_metadata"].get("route_taken") in ("vector", "both")
    ]
    out: Dict[str, Any] = {
        "n_paired": len(ids),
        "routes": {
            i: {
                "baseline": base[i]["adapter_metadata"].get("route_taken"),
                "optimized": opt[i]["adapter_metadata"].get("route_taken"),
            }
            for i in ids
        },
        "adr033_affected_ids": vector_ids,
        "metrics": {},
    }
    for metric in STORED_JUDGE_METRICS:
        for label, subset in (("all", ids), ("vector_routed", vector_ids)):
            deltas = [
                opt[i]["scores"][metric] - base[i]["scores"][metric]
                for i in subset
                if metric in opt[i]["scores"] and metric in base[i]["scores"]
            ]
            mean, lo, hi = bootstrap_ci(deltas)
            out["metrics"][f"{metric}|{label}"] = {
                "n": len(deltas),
                "baseline_mean": statistics.fmean(base[i]["scores"][metric] for i in subset)
                if subset else float("nan"),
                "optimized_mean": statistics.fmean(opt[i]["scores"][metric] for i in subset)
                if subset else float("nan"),
                "mean_delta": mean,
                "ci95": [lo, hi],
                "significant": bool(deltas) and (lo > 0 or hi < 0),
            }
    return out


# ---------------------------------------------------------------------------
# 3. Fresh capture + objective (judge-free) outcomes
# ---------------------------------------------------------------------------
def load_dataset(path: Path, limit: int) -> List[Dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit]


async def _fetch_corpus() -> List[Dict[str, str]]:
    from sqlalchemy import text

    from src.vector.indexer import VectorStore

    vs = VectorStore()
    async with vs.session_factory() as s:
        res = await s.execute(text("SELECT chunk_id, paper_title, text FROM document_chunks"))
        return [dict(r) for r in res.mappings().all()]


def capture_fresh(rows: List[Dict[str, Any]], api_url: str) -> List[Dict[str, Any]]:
    """Run the benchmark adapter live (cache off, one session per question) and keep raw context."""
    from eval_adapter import GraphRAGAdapter

    adapter = GraphRAGAdapter(api_url=api_url, use_cache=False)
    captured = []
    for row in rows:
        meta = dict(row["metadata"])
        meta["session_id"] = f"validate_{meta['id']}"
        t0 = time.time()
        resp = adapter.run(row["input"], meta)
        captured.append({
            "id": meta["id"],
            "question": row["input"],
            "reference": row["reference"],
            "expected_keywords": meta.get("expected_keywords", []),
            "should_refuse": bool(meta.get("should_refuse", False)),
            "answer": resp.output,
            "context": resp.context,
            "route": resp.metadata.get("route_taken"),
            "citations": resp.metadata.get("citations", []),
            "latency_s": round(time.time() - t0, 1),
        })
        print(f"  captured {meta['id']} route={captured[-1]['route']} ctx={len(resp.context)}", flush=True)
    return captured


def objective_outcomes(captured: List[Dict[str, Any]], corpus: List[Dict[str, str]]) -> None:
    """Annotate each captured example in place with judge-free correctness signals."""
    for ex in captured:
        kws = [k for k in ex["expected_keywords"] if k]
        ans_l = ex["answer"].lower()
        ex["kw_recall"] = (
            sum(k.lower() in ans_l for k in kws) / len(kws) if kws else float("nan")
        )
        ex["abstained"] = bool(ABSTAIN_RE.search(ex["answer"]))
        best_cov, best_id = 0.0, None
        for ch in corpus:
            txt = ch["text"].lower()
            cov = sum(k.lower() in txt for k in kws) / len(kws) if kws else 0.0
            if cov > best_cov:
                best_cov, best_id = cov, ch["chunk_id"]
        ex["corpus_best_coverage"] = best_cov
        ex["corpus_best_chunk"] = best_id
        ex["answerable_in_text_corpus"] = best_cov >= KEYWORD_CORRECT_RECALL
        if ex["should_refuse"]:
            ex["outcome"] = "correct_refusal" if ex["abstained"] else "should_have_refused"
        elif ex["abstained"]:
            ex["outcome"] = (
                "missed_answerable_abstained" if ex["answerable_in_text_corpus"] else "abstained_not_in_text"
            )
        else:
            ex["outcome"] = "keyword_correct" if ex["kw_recall"] >= KEYWORD_CORRECT_RECALL else "keyword_wrong"
        ctx_text = ex["context"]
        used = sum(_lexical_overlap(c, ex["answer"]) >= CHUNK_UTIL_THRESHOLD for c in ctx_text)
        ex["chunk_utilization_recomputed"] = used / len(ctx_text) if ctx_text else float("nan")


# ---------------------------------------------------------------------------
# 4/5. Judge repeatability + cross-judge
# ---------------------------------------------------------------------------
def legacy_parse(content: str) -> Tuple[float, str]:
    """Faithful copy of OpenAICompatibleJudge.score's parse chain -> (score, path_taken)."""
    try:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        return max(0.0, min(1.0, float(data["score"]))), "json"
    except Exception:  # noqa: BLE001 - deliberate mirror of production behaviour
        m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', content)
        if m:
            return max(0.0, min(1.0, float(m.group(1)))), "regex_labeled"
        m2 = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", content)
        if m2:
            return float(m2.group(1)), "regex_loose_number"
        return 0.5, "fallback_0.5"


def strict_parse(content: str) -> Optional[float]:
    """Strict parse: valid JSON with numeric score in [0,1], else None (never defaults)."""
    try:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
        score = json.loads(cleaned)["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0:
            return None
        return float(score)
    except Exception:  # noqa: BLE001
        return None


class RawJudge:
    """OpenAI-compatible judge that returns the RAW reply so nothing is hidden."""

    def __init__(self, model: str) -> None:
        import openai

        self.model = model
        self.client = openai.OpenAI(
            base_url=os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            timeout=JUDGE_TIMEOUT_S,
            max_retries=2,
        )

    def call(self, prompt: str) -> Dict[str, Any]:
        import openai

        last_error = ""
        for attempt in range(len(JUDGE_BACKOFF_S) + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt.rstrip() + JUDGE_JSON_SUFFIX}],
                    temperature=0.0,
                )
                raw = resp.choices[0].message.content or ""
                break
            except openai.RateLimitError as exc:
                # 429: back off and retry; only give up after the full schedule is exhausted.
                last_error = f"{type(exc).__name__}: {exc}"[:300]
                if attempt < len(JUDGE_BACKOFF_S):
                    time.sleep(JUDGE_BACKOFF_S[attempt])
                    continue
                return {"raw": "", "error": last_error, "strict": None,
                        "legacy": None, "legacy_path": "api_error"}
            except Exception as exc:  # noqa: BLE001 - surfaced in report, not swallowed
                return {"raw": "", "error": f"{type(exc).__name__}: {exc}"[:300], "strict": None,
                        "legacy": None, "legacy_path": "api_error"}
        legacy, path = legacy_parse(raw)
        return {"raw": raw, "error": None, "strict": strict_parse(raw), "legacy": legacy,
                "legacy_path": path}


def _prompts_for(ex: Dict[str, Any]) -> Dict[str, str]:
    ctx = "\n---\n".join(ex["context"]) or "(no context retrieved)"
    return {
        "faithfulness": _FAITHFULNESS_PROMPT.format(context=ctx, answer=ex["answer"]),
        "context_precision": _CONTEXT_PRECISION_PROMPT.format(question=ex["question"], context=ctx),
        "answer_relevancy": _ANSWER_RELEVANCY_PROMPT.format(question=ex["question"], answer=ex["answer"]),
    }


def run_judge(model: str, captured: List[Dict[str, Any]], repeats: int) -> Dict[str, Any]:
    judge = RawJudge(model)
    jobs = [
        (ex["id"], metric, rep, prompt)
        for ex in captured
        for metric, prompt in _prompts_for(ex).items()
        for rep in range(repeats)
    ]

    def _do(job: Tuple[str, str, int, str]) -> Tuple[str, str, int, Dict[str, Any]]:
        qid, metric, rep, prompt = job
        return qid, metric, rep, judge.call(prompt)

    out: Dict[str, Any] = {"model": model, "calls": []}
    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        for qid, metric, rep, res in pool.map(_do, jobs):
            out["calls"].append({"id": qid, "metric": metric, "rep": rep, **res})
    return out


def _ranks(values: List[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a: List[float], b: List[float]) -> Optional[float]:
    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return None
    return statistics.correlation(_ranks(a), _ranks(b))


def summarise_judge(judge_out: Dict[str, Any]) -> Dict[str, Any]:
    calls = judge_out["calls"]
    per_item: Dict[Tuple[str, str], List[float]] = {}
    paths: Counter = Counter()
    strict_fail = 0
    for c in calls:
        paths[c["legacy_path"]] += 1
        if c["strict"] is None:
            strict_fail += 1
        else:
            per_item.setdefault((c["id"], c["metric"]), []).append(c["strict"])
    stds = {
        m: statistics.fmean(
            statistics.pstdev(v) for (q, mm), v in per_item.items() if mm == m and len(v) > 1
        ) if any(mm == m and len(v) > 1 for (q, mm), v in per_item.items()) else float("nan")
        for m in ("faithfulness", "context_precision", "answer_relevancy")
    }
    means = {
        f"{q}|{m}": statistics.fmean(v) for (q, m), v in per_item.items()
    }
    return {
        "n_calls": len(calls),
        "strict_parse_failures": strict_fail,
        "legacy_parse_paths": dict(paths),
        "mean_within_item_std": stds,
        "item_means": means,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def build_report(ev: Dict[str, Any]) -> str:
    L: List[str] = ["# Benchmark Validation Report", "", f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')}_", ""]
    d = ev["deterministic"]
    L += ["## 1. Deterministic recompute (stored vs independent implementation)", "",
          "| run | n | max abs F1 diff | EM mismatches |", "|---|---|---|---|"]
    for name, res in d.items():
        L.append(f"| {name} | {len(res['rows'])} | {res['max_abs_f1_diff']:.2e} | {res['em_mismatches']} |")
    pc = ev["paired"]
    L += ["", "## 2. Paired comparison baseline -> optimized (bootstrap 95% CI)", "",
          f"Paired questions: {pc['n_paired']}. ADR-033-affected (vector/both route in optimized run): "
          f"{pc['adr033_affected_ids']}", "",
          "| metric | subset | n | baseline | optimized | mean delta | 95% CI | significant |",
          "|---|---|---|---|---|---|---|---|"]
    for key, m in pc["metrics"].items():
        metric, subset = key.split("|")
        L.append(f"| {metric} | {subset} | {m['n']} | {m['baseline_mean']:.3f} | {m['optimized_mean']:.3f} | "
                 f"{m['mean_delta']:+.3f} | [{m['ci95'][0]:+.3f}, {m['ci95'][1]:+.3f}] | {m['significant']} |")
    L += ["", "Routes per question (baseline -> optimized):", ""]
    for qid, r in pc["routes"].items():
        L.append(f"- {qid}: {r['baseline']} -> {r['optimized']}")
    L += ["", "## 3. Objective (judge-free) outcomes on fresh live capture", "",
          "| id | route | outcome | kw_recall | answerable in text corpus | best chunk | chunk_util (recomputed) |",
          "|---|---|---|---|---|---|---|"]
    for ex in ev["captured"]:
        L.append(f"| {ex['id']} | {ex['route']} | {ex['outcome']} | {ex['kw_recall']:.2f} | "
                 f"{ex['answerable_in_text_corpus']} ({ex['corpus_best_coverage']:.2f}) | "
                 f"{ex['corpus_best_chunk']} | {ex['chunk_utilization_recomputed']:.2f} |")
    oc = Counter(ex["outcome"] for ex in ev["captured"])
    L += ["", f"Outcome counts: {dict(oc)}", ""]
    for label in ("primary", "alt"):
        js = ev["judges"].get(label)
        if not js:
            continue
        s = js["summary"]
        L += [f"## 4{'a' if label == 'primary' else 'b'}. Judge `{js['model']}` ({label})", "",
              f"- calls: {s['n_calls']}, strict-parse failures: {s['strict_parse_failures']}",
              f"- production-parser paths: {s['legacy_parse_paths']}",
              f"- mean within-item std over {JUDGE_REPEATS} repeats (temp 0): {s['mean_within_item_std']}", ""]
    if "agreement" in ev:
        L += ["## 5. Cross-judge agreement (primary vs alt, item-level means)", "",
              "| metric | Spearman | mean |primary-alt| |", "|---|---|---|"]
        for m, a in ev["agreement"].items():
            sp = "n/a" if a["spearman"] is None else f"{a['spearman']:.2f}"
            L.append(f"| {m} | {sp} | {a['mean_abs_diff']:.3f} |")
        L += ["", "Per-question item means (primary / alt):", "",
              "| id | faith P | faith A | prec P | prec A | rel P | rel A |", "|---|---|---|---|---|---|---|"]
        pm = ev["judges"]["primary"]["summary"]["item_means"]
        am = ev["judges"]["alt"]["summary"]["item_means"]
        for ex in ev["captured"]:
            row = [ex["id"]]
            for m in ("faithfulness", "context_precision", "answer_relevancy"):
                for src in (pm, am):
                    v = src.get(f"{ex['id']}|{m}")
                    row.append("n/a" if v is None else f"{v:.2f}")
            L.append("| " + " | ".join(row) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--optimized", type=Path, required=True)
    ap.add_argument("--dataset", type=Path, default=_REPO_ROOT / "data" / "evalkit_dataset.jsonl")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--primary-judge", default=os.getenv("EXTRACTION_MODEL", "nvidia/nemotron-3-super-120b-a12b"))
    ap.add_argument("--alt-judge", default=DEFAULT_ALT_JUDGE)
    ap.add_argument("--api-url", default=DEFAULT_API_URL)
    ap.add_argument("--repeats", type=int, default=JUDGE_REPEATS)
    ap.add_argument("--reuse-capture", action="store_true", help="Reuse previously captured examples from output-dir")
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    base, opt = load_results(args.baseline), load_results(args.optimized)
    ev: Dict[str, Any] = {
        "deterministic": {"baseline": check_deterministic(base), "optimized": check_deterministic(opt)},
        "paired": paired_comparison(base, opt),
        "judges": {},
    }
    print("[1/4] deterministic + paired done", flush=True)

    print("[2/4] live capture + objective outcomes", flush=True)
    prev_file = args.output_dir / "validation_results.json"
    if args.reuse_capture and prev_file.exists():
        prev_data = json.loads(prev_file.read_text(encoding="utf-8"))
        captured = prev_data.get("captured", [])
        print(f"  Reusing {len(captured)} previously captured examples", flush=True)
    else:
        rows = load_dataset(args.dataset, args.limit)
        captured = capture_fresh(rows, args.api_url)
        objective_outcomes(captured, asyncio.run(_fetch_corpus()))
    ev["captured"] = captured

    print("[3/4] primary judge repeats", flush=True)
    p = run_judge(args.primary_judge, captured, args.repeats)
    p["summary"] = summarise_judge(p)
    ev["judges"]["primary"] = p

    print("[4/4] alternate judge repeats", flush=True)
    a = run_judge(args.alt_judge, captured, args.repeats)
    a["summary"] = summarise_judge(a)
    ev["judges"]["alt"] = a

    ev["agreement"] = {}
    for m in ("faithfulness", "context_precision", "answer_relevancy"):
        keys = [k for k in p["summary"]["item_means"] if k.endswith(f"|{m}") and k in a["summary"]["item_means"]]
        x = [p["summary"]["item_means"][k] for k in keys]
        y = [a["summary"]["item_means"][k] for k in keys]
        ev["agreement"][m] = {
            "n": len(keys),
            "spearman": spearman(x, y),
            "mean_abs_diff": statistics.fmean(abs(i - j) for i, j in zip(x, y)) if keys else float("nan"),
        }

    (args.output_dir / "validation_results.json").write_text(json.dumps(ev, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "validation_report.md").write_text(build_report(ev), encoding="utf-8")
    print(f"done -> {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
