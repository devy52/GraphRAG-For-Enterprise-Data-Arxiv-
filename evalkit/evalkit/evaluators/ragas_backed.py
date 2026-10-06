from __future__ import annotations

import asyncio
from typing import Any, Optional

from evalkit.contracts.evaluator import BaseEvaluator
from evalkit.contracts.judge_backend import BaseJudgeBackend

try:
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecision,
        ContextUtilization,
        Faithfulness,
    )

    _RAGAS_AVAILABLE = True
except ImportError:
    _RAGAS_AVAILABLE = False


class RagasEvaluator(BaseEvaluator):
    """RAG evaluator backed by ragas's own peer-reviewed metric implementations.

    Requires the optional extra: ``pip install evalkit[ragas]``. Same
    ``BaseEvaluator`` contract as the built-in ``RagEvaluator`` — swap
    ``track: rag`` for ``track: ragas`` in config, no other changes needed.

    Provider note — the actual tradeoff of using ragas's metrics: unlike
    the built-in RagEvaluator (fully provider-agnostic via evalkit's
    LiteLLM-based judge_backend), ragas manages its own LLM and embedding
    calls. This defaults to OpenAI (reads OPENAI_API_KEY the normal way).
    For another provider, pass your own ``ragas_client`` via
    ``evaluator_config`` in your YAML config, pointed at any
    OpenAI-compatible endpoint (e.g. a local ``litellm --model <provider/model>``
    proxy) — see ragas's own LLM Adapters guide for provider-specific setup.

    context_precision uses ContextUtilization (reference-free) when the
    example has no `reference`, and the more accurate ContextPrecision
    (reference-based) when it does — matching evalkit's reference-free
    default without discarding a reference answer if one is available.
    """

    ALL_METRICS = ("faithfulness", "context_precision", "answer_relevancy", "hallucination_rate")

    METRIC_DESCRIPTIONS = {
        "faithfulness": (
            "Computed by ragas's Faithfulness metric: LLM-judged, 0.0-1.0, verifies "
            "each claim in the response against the retrieved context."
        ),
        "context_precision": (
            "Computed by ragas: ContextUtilization (reference-free) if the dataset "
            "has no reference answer, otherwise the more accurate reference-based ContextPrecision."
        ),
        "answer_relevancy": (
            "Computed by ragas's AnswerRelevancy metric: embedding-similarity based, "
            "scores how relevant the answer is to the original question."
        ),
        "hallucination_rate": (
            "1.0 - faithfulness, reusing ragas's Faithfulness computation (no extra cost)."
        ),
    }

    def __init__(
        self,
        judge: Optional[BaseJudgeBackend] = None,  # unused — ragas manages its own LLM calls;
        # kept so the runner can construct this the same way as any other evaluator.
        metrics: Optional[list[str]] = None,
        ragas_model: str = "gpt-4o-mini",
        ragas_embedding_model: str = "text-embedding-3-small",
        ragas_client: Any = None,
    ) -> None:
        if not _RAGAS_AVAILABLE:
            raise ImportError(
                "RagasEvaluator requires the 'ragas' extra: pip install evalkit[ragas]"
            )
        self.metrics = metrics or list(self.ALL_METRICS)
        needs_faithfulness = "faithfulness" in self.metrics or "hallucination_rate" in self.metrics

        if ragas_client is None:
            from openai import AsyncOpenAI

            ragas_client = AsyncOpenAI()  # reads OPENAI_API_KEY

        llm = llm_factory(ragas_model, client=ragas_client)

        self._faithfulness = Faithfulness(llm=llm) if needs_faithfulness else None
        if "context_precision" in self.metrics:
            self._context_precision_ref = ContextPrecision(llm=llm)
            self._context_utilization = ContextUtilization(llm=llm)
        else:
            self._context_precision_ref = None
            self._context_utilization = None
        if "answer_relevancy" in self.metrics:
            embeddings = embedding_factory("openai", model=ragas_embedding_model, client=ragas_client)
            self._answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
        else:
            self._answer_relevancy = None

    def evaluate(
        self,
        example_input: str,
        output: str,
        reference: Optional[str],
        context: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> dict[str, float]:
        return asyncio.run(self._ascore(example_input, output, reference, context or []))

    async def _ascore(
        self, example_input: str, output: str, reference: Optional[str], contexts: list[str]
    ) -> dict[str, float]:
        scores: dict[str, float] = {}

        if self._faithfulness is not None:
            result = await self._faithfulness.ascore(
                user_input=example_input, response=output, retrieved_contexts=contexts
            )
            faithfulness_score = float(result.value)
            if "faithfulness" in self.metrics:
                scores["faithfulness"] = faithfulness_score
            if "hallucination_rate" in self.metrics:
                scores["hallucination_rate"] = 1.0 - faithfulness_score

        if self._context_utilization is not None:
            if reference:
                result = await self._context_precision_ref.ascore(
                    user_input=example_input, reference=reference, retrieved_contexts=contexts
                )
            else:
                result = await self._context_utilization.ascore(
                    user_input=example_input, response=output, retrieved_contexts=contexts
                )
            scores["context_precision"] = float(result.value)

        if self._answer_relevancy is not None:
            result = await self._answer_relevancy.ascore(user_input=example_input, response=output)
            scores["answer_relevancy"] = float(result.value)

        return scores
