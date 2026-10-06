#!/usr/bin/env python3
"""
Three-way evaluation harness for a single, frozen GraphRAG output snapshot.

Design invariant:
    GraphRAG is executed ONCE per question. The exact captured question, answer,
    retrieval context, reference, and GraphRAG metadata are then reused by
    Evalkit, Ragas, and DeepEval. No evaluator is allowed to re-query the app.

Phases:
    1. capture  -> data/eval_framework_snapshot.jsonl
    2. evaluate -> data/eval_framework_comparison_3way.json/.md

The three frameworks are deliberately treated as independent evaluators. A
score gap is evaluator disagreement, not calibration error or proof of truth.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evalkit"))
sys.path.insert(0, str(ROOT / "evalharness"))
sys.path.insert(0, str(ROOT / "evalkit_upgraded"))

from eval_adapter import GraphRAGAdapter
try:
    from evalkit.evaluators.graph import GraphEvaluator
    from evalkit.evaluators.rag import RagEvaluator
    from evalkit.judges.litellm_judge import LiteLLMJudge
except ImportError:
    from evalharness.evaluators.graph import GraphEvaluator
    from evalharness.evaluators.rag import RagEvaluator
    from evalharness.judges.litellm_judge import LiteLLMJudge
from src.core.config import get_settings

COMMON = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
DEEP = ["faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]


def finite(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return round(v, 4)


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def stratify(rows: List[Dict[str, Any]], per_hop: int) -> List[Dict[str, Any]]:
    order = ["1-hop", "2-hop", "3-hop", "aggregation", "out-of-scope"]
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row.get("hop_type", "unknown"), []).append(row)
    selected: List[Dict[str, Any]] = []
    for hop in order:
        selected.extend(groups.get(hop, [])[:per_hop])
    for hop, items in groups.items():
        if hop not in order:
            selected.extend(items[:per_hop])
    return selected


def capture_snapshot(dataset: Path, snapshot_path: Path, per_hop: int, timeout: float) -> None:
    rows = stratify(load_dataset(dataset), per_hop)
    if not rows:
        raise SystemExit("No benchmark rows selected.")

    adapter = GraphRAGAdapter(timeout_seconds=timeout, use_cache=False)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc).isoformat()

    with snapshot_path.open("w", encoding="utf-8") as fh:
        for i, q in enumerate(rows, 1):
            qid = q["id"]
            print(f"[capture {i}/{len(rows)}] {qid}: {q['question'][:70]}")
            start = time.perf_counter()
            resp = adapter.run(q["question"], metadata=q)
            elapsed = round((time.perf_counter() - start) * 1000.0, 1)
            record = {
                "schema_version": "graphrag-eval-snapshot-v1",
                "captured_at": captured_at,
                "id": qid,
                "hop_type": q.get("hop_type", "unknown"),
                "question": q["question"],
                "answerable": q.get("answerable", True),
                "reference": q.get("reference_answer", ""),
                "required_facts": q.get("required_facts", []),
                "gold_chunk_ids": q.get("gold_chunk_ids", []),
                "response": resp.output or "(no response)",
                "retrieval_context": list(resp.context or []),
                "latency_ms": finite(resp.latency_ms or elapsed) or elapsed,
                "metadata": dict(resp.metadata or {}),
            }
            # Never persist benchmark gold into the application context itself.
            for forbidden in ("expected_answer_keywords", "reference_answer"):
                record["metadata"].pop(forbidden, None)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Snapshot saved: {snapshot_path} ({len(rows)} records)")


class NvidiaOpenAICompatibleModel:
    """Tiny DeepEvalBaseLLM wrapper for any OpenAI-compatible gateway."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from openai import AsyncOpenAI, OpenAI
        self.model_name = model
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)
        self.async_client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=120.0)

    def load_model(self):
        return self.client

    def get_model_name(self) -> str:
        return self.model_name

    @staticmethod
    def _extract_json(text: str) -> Any:
        text = (text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try finding outermost balanced JSON object or array
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try raw_decode from first opening brace or bracket
        for i, ch in enumerate(text):
            if ch in "{[":
                try:
                    obj, _ = json.JSONDecoder().raw_decode(text[i:])
                    return obj
                except json.JSONDecodeError:
                    continue
        return json.loads(text)

    def generate(self, prompt: str, schema: Any = None) -> Any:
        max_attempts = 3
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                kwargs = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                }
                result = self.client.chat.completions.create(**kwargs)
                content = result.choices[0].message.content or ""
                if schema is None:
                    return content
                data = self._extract_json(content)
                return schema.model_validate(data)
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts:
                    time.sleep(1.0 * attempt)
        raise last_exc

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        max_attempts = 3
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                kwargs = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                }
                result = await self.async_client.chat.completions.create(**kwargs)
                content = result.choices[0].message.content or ""
                if schema is None:
                    return content
                data = self._extract_json(content)
                return schema.model_validate(data)
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts:
                    await asyncio.sleep(1.0 * attempt)
        raise last_exc


def load_snapshot(path: Path) -> List[Dict[str, Any]]:
    return load_dataset(path)


def evaluate_evalkit(snapshot: List[Dict[str, Any]]) -> Dict[str, Any]:
    settings = get_settings()
    judge = LiteLLMJudge(
        model="openai/" + settings.synthesis_model,
        api_base=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    rag = RagEvaluator(judge=judge, metrics=COMMON)
    graph = GraphEvaluator(judge=judge, metrics=["graph_utilization_rate", "global_diversity"])
    output: Dict[str, Any] = {}

    for row in snapshot:
        metadata = dict(row.get("metadata") or {})
        scores = rag.evaluate(
            example_input=row["question"],
            output=row["response"],
            reference=row.get("reference", ""),
            context=row.get("retrieval_context", []),
            metadata=metadata,
        )
        scores.update(graph.evaluate(
            example_input=row["question"],
            output=row["response"],
            reference=row.get("reference", ""),
            context=row.get("retrieval_context", []),
            metadata=metadata,
        ))
        output[row["id"]] = {k: finite(v) for k, v in scores.items() if finite(v) is not None}
    return output


def evaluate_ragas(snapshot: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            answer_relevancy as answer_relevancy,
            context_precision as context_precision,
            context_recall as context_recall,
            faithfulness as faithfulness,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Ragas evaluation dependencies are unavailable. Install requirements-evaluation.txt."
        ) from exc

    settings = get_settings()
    dataset = Dataset.from_dict({
        "user_input": [r["question"] for r in snapshot],
        "response": [r["response"] for r in snapshot],
        "retrieved_contexts": [r["retrieval_context"] or ["(no context)"] for r in snapshot],
        "reference": [r.get("reference", "") for r in snapshot],
    })
    llm = ChatOpenAI(
        model=settings.synthesis_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
    )
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        check_embedding_ctx_length=False,
    )
    result = ragas_evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
    )
    df = result.to_pandas()
    out: Dict[str, Any] = {}
    for i, row in df.iterrows():
        out[snapshot[i]["id"]] = {
            "faithfulness": finite(row.get("faithfulness")),
            "answer_relevancy": finite(row.get("answer_relevancy")),
            "context_precision": finite(row.get("context_precision")),
            "context_recall": finite(row.get("context_recall")),
        }
    return out


def evaluate_deepeval(snapshot: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            FaithfulnessMetric,
        )
        from deepeval.test_case import LLMTestCase
        from deepeval.models.base_model import DeepEvalBaseLLM
    except ImportError as exc:
        raise RuntimeError(
            "DeepEval is unavailable. Install requirements-evaluation.txt."
        ) from exc

    # Reuse the custom model implementation while making it an actual DeepEvalBaseLLM.
    class DeepEvalNvidiaModel(DeepEvalBaseLLM):
        def __init__(self, base_url: str, api_key: str, model: str) -> None:
            self.inner = NvidiaOpenAICompatibleModel(base_url, api_key, model)

        def load_model(self):
            return self.inner.load_model()

        def generate(self, prompt: str, schema: Any = None) -> Any:
            return self.inner.generate(prompt, schema)

        async def a_generate(self, prompt: str, schema: Any = None) -> Any:
            return await self.inner.a_generate(prompt, schema)

        def get_model_name(self) -> str:
            return self.inner.get_model_name()

    settings = get_settings()
    model = DeepEvalNvidiaModel(settings.llm_base_url, settings.llm_api_key, settings.synthesis_model)
    metric_factories = {
        "faithfulness": lambda: FaithfulnessMetric(model=model, threshold=None, include_reason=True, async_mode=False),
        "answer_relevancy": lambda: AnswerRelevancyMetric(model=model, threshold=None, include_reason=True, async_mode=False),
        "contextual_precision": lambda: ContextualPrecisionMetric(model=model, threshold=None, include_reason=True, async_mode=False),
        "contextual_recall": lambda: ContextualRecallMetric(model=model, threshold=None, include_reason=True, async_mode=False),
    }
    out: Dict[str, Any] = {}
    for row in snapshot:
        case = LLMTestCase(
            input=row["question"],
            actual_output=row["response"],
            expected_output=row.get("reference", ""),
            retrieval_context=row.get("retrieval_context", []) or ["(no context)"],
        )
        item: Dict[str, Any] = {}
        for name, factory in metric_factories.items():
            start_t = time.perf_counter()
            metric = factory()
            attempts = 0
            success = False
            last_err = None
            for attempt in range(1, 4):
                attempts = attempt
                try:
                    metric.measure(case)
                    item[name] = finite(metric.score)
                    item[f"{name}_reason"] = getattr(metric, "reason", None)
                    success = True
                    break
                except Exception as exc:
                    last_err = exc
                    if attempt < 3:
                        time.sleep(2.0 * attempt)
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            item[f"{name}_telemetry"] = {
                "attempts": attempts,
                "final_status": "success" if success else "error",
                "latency_ms": elapsed_ms,
                "error": f"{type(last_err).__name__}: {last_err}" if not success else None,
            }
            if not success:
                item[name] = None
                item[f"{name}_error"] = f"{type(last_err).__name__}: {last_err}"
        out[row["id"]] = item
    return out


def summarize(snapshot: List[Dict[str, Any]], scores: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for metric in COMMON:
        vals = []
        for qid in scores:
            v = finite(scores[qid].get(metric))
            if v is not None:
                vals.append(v)
        result[metric] = {
            "mean": round(sum(vals) / len(vals), 4) if vals else None,
            "n": len(vals),
            "total": len(snapshot),
        }
    return result


def score_gap(a: Any, b: Any) -> Optional[float]:
    a = finite(a); b = finite(b)
    return round(a - b, 4) if a is not None and b is not None else None


def run_evaluation(snapshot_path: Path, out_json: Path, out_md: Path) -> None:
    snapshot = load_snapshot(snapshot_path)
    if not snapshot:
        raise SystemExit("Snapshot is empty.")

    evalkit = evaluate_evalkit(snapshot)
    ragas = evaluate_ragas(snapshot)
    deepeval = evaluate_deepeval(snapshot)

    per_question: List[Dict[str, Any]] = []
    for row in snapshot:
        qid = row["id"]
        per_question.append({
            "id": qid,
            "hop_type": row.get("hop_type"),
            "question": row["question"],
            "reference": row.get("reference", ""),
            "response": row["response"],
            "context_count": len(row.get("retrieval_context", [])),
            "route_taken": (row.get("metadata") or {}).get("route_taken"),
            "evalkit": evalkit.get(qid, {}),
            "ragas": ragas.get(qid, {}),
            "deepeval": deepeval.get(qid, {}),
            "score_gaps": {
                "evalkit_minus_ragas": {m: score_gap(evalkit.get(qid, {}).get(m), ragas.get(qid, {}).get(m)) for m in COMMON},
                "evalkit_minus_deepeval": {m: score_gap(evalkit.get(qid, {}).get(m), deepeval.get(qid, {}).get({
                    "context_precision": "contextual_precision",
                    "context_recall": "contextual_recall",
                    "faithfulness": "faithfulness",
                    "answer_relevancy": "answer_relevancy",
                }.get(m, m))) for m in COMMON},
            },
        })

    summary = {
        "evalkit": summarize(snapshot, evalkit),
        "ragas": summarize(snapshot, ragas),
        "deepeval": summarize(snapshot, {
            qid: {
                "faithfulness": d.get("faithfulness"),
                "answer_relevancy": d.get("answer_relevancy"),
                "context_precision": d.get("contextual_precision"),
                "context_recall": d.get("contextual_recall"),
            }
            for qid, d in deepeval.items()
        }),
    }

    snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    payload = {
        "schema_version": "3way-evaluation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": str(snapshot_path),
        "snapshot_sha256": snapshot_sha256,
        "question_count": len(snapshot),
        "frameworks": ["evalkit", "ragas", "deepeval"],
        "common_metrics": COMMON,
        "summary": summary,
        "per_question": per_question,
        "methodology_note": (
            "All three frameworks evaluated the same frozen GraphRAG outputs. "
            "Pairwise differences are evaluator score gaps, not calibration error or proof of truth."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# GraphRAG 3-Way Evaluation: Evalkit vs Ragas vs DeepEval",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Snapshot: `{snapshot_path}`",
        f"Snapshot SHA-256: `{snapshot_sha256}`",
        f"Questions: **{len(snapshot)}**",
        "",
        "> The same frozen GraphRAG outputs, retrieval contexts, references, and metadata were supplied to all three frameworks. Score differences are evaluator disagreement, not a truth/calibration error.",
        "",
        "## Aggregate common metrics",
        "",
        "| Metric | Evalkit | Ragas | DeepEval |",
        "|---|---:|---:|---:|",
    ]
    for m in COMMON:
        def f(framework: str, key: str = m) -> str:
            v = summary[framework].get(key, {}).get("mean")
            n = summary[framework].get(key, {}).get("n", 0)
            tot = summary[framework].get(key, {}).get("total", len(snapshot))
            return f"N/A ({n}/{tot})" if v is None else f"{v:.4f} ({n}/{tot})"
        lines.append(f"| `{m}` | {f('evalkit')} | {f('ragas')} | {f('deepeval')} |")
    lines.extend(["", "## Per-question comparison", "", "| ID | Tier | Evalkit faith. | Ragas faith. | DeepEval faith. | Evalkit rel. | Ragas rel. | DeepEval rel. |", "|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in per_question:
        ek=row["evalkit"]; rg=row["ragas"]; dp=row["deepeval"]
        def ff(v): return "N/A" if v is None else f"{v:.3f}"
        lines.append(f"| `{row['id']}` | {row['hop_type']} | {ff(ek.get('faithfulness'))} | {ff(rg.get('faithfulness'))} | {ff(dp.get('faithfulness'))} | {ff(ek.get('answer_relevancy'))} | {ff(rg.get('answer_relevancy'))} | {ff(dp.get('answer_relevancy'))} |")
    lines.extend([
        "",
        "## Important interpretation rules",
        "",
        "1. Faithfulness / groundedness is not factual truth.",
        "2. Answer relevancy is not answer completeness or correctness.",
        "3. Context precision/recall depend on how references and contexts are represented.",
        "4. DeepEval custom-model JSON failures are recorded as `null`/error rather than converted to zero.",
        "5. The snapshot is the reproducibility boundary: rerunning a framework without re-running GraphRAG is allowed; silently re-querying GraphRAG is not.",
    ])
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {out_json}")
    print(f"Saved: {out_md}")


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate one frozen GraphRAG output snapshot with Evalkit, Ragas and DeepEval.")
    p.add_argument("--dataset", default="data/benchmark_v2_dataset.jsonl")
    p.add_argument("--snapshot", default="data/eval_framework_snapshot.jsonl")
    p.add_argument("--output-json", default="data/eval_framework_comparison_3way.json")
    p.add_argument("--output-md", default="data/eval_framework_comparison_3way.md")
    p.add_argument("--per-hop", type=int, default=1)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--capture-only", action="store_true")
    p.add_argument("--evaluate-only", action="store_true")
    args = p.parse_args()

    snapshot = Path(args.snapshot)
    if not args.evaluate_only:
        capture_snapshot(Path(args.dataset), snapshot, args.per_hop, args.timeout)
    if args.capture_only:
        return
    if not snapshot.exists():
        raise SystemExit(f"Snapshot not found: {snapshot}")
    run_evaluation(snapshot, Path(args.output_json), Path(args.output_md))


if __name__ == "__main__":
    main()
