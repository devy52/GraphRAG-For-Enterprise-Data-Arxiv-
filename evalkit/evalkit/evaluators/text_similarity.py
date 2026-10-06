from __future__ import annotations

import math
import re
from typing import Any, Optional

from evalkit.contracts.evaluator import BaseEvaluator
from evalkit.contracts.judge_backend import BaseJudgeBackend

try:
    import sacrebleu

    _SACREBLEU_AVAILABLE = True
except ImportError:
    _SACREBLEU_AVAILABLE = False

try:
    from rouge_score import rouge_scorer

    _ROUGE_AVAILABLE = True
except ImportError:
    _ROUGE_AVAILABLE = False

try:
    import bert_score

    _BERTSCORE_AVAILABLE = True
except ImportError:
    _BERTSCORE_AVAILABLE = False



def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _token_f1(output: str, reference: str) -> float:
    """SQuAD-style token-overlap F1. Pure stdlib, no dependency."""
    output_tokens = _tokenize(output)
    reference_tokens = _tokenize(reference)
    if not output_tokens or not reference_tokens:
        return 1.0 if output_tokens == reference_tokens else 0.0

    common: dict[str, int] = {}
    for t in output_tokens:
        if t in reference_tokens:
            common[t] = common.get(t, 0) + 1
    overlap = 0
    ref_counts: dict[str, int] = {}
    for t in reference_tokens:
        ref_counts[t] = ref_counts.get(t, 0) + 1
    out_counts: dict[str, int] = {}
    for t in output_tokens:
        out_counts[t] = out_counts.get(t, 0) + 1
    for t, c in out_counts.items():
        overlap += min(c, ref_counts.get(t, 0))

    if overlap == 0:
        return 0.0
    precision = overlap / len(output_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class TextSimilarityEvaluator(BaseEvaluator):
    """Deterministic reference-based text metrics — no LLM judge calls except
    for embedding_similarity (which uses embeddings, not a judge model).
    Every metric here requires a `reference` in the dataset; examples
    without one score nothing (not an error — just no signal to compare
    against).

    bleu and rouge_l need the optional extra: pip install evalkit[text-metrics]
    exact_match and f1 have zero dependencies beyond the standard library.
    embedding_similarity uses LiteLLM's embedding endpoint (same provider
    story as evalkit's judge backend — any provider, via a plain model
    string), not the judge_backend/judge_model config (those are for
    LLM-as-judge scoring, this is a raw embedding call).
    """

    ALL_METRICS = ("exact_match", "f1", "bleu", "rouge_l", "bert_score", "embedding_similarity")

    METRIC_DESCRIPTIONS = {
        "exact_match": "1.0 if output exactly matches reference (whitespace-trimmed), else 0.0.",
        "f1": "SQuAD-style token-overlap F1 between output and reference. Deterministic, no LLM call.",
        "bleu": "Sentence-level BLEU score (sacrebleu), normalized to 0.0-1.0. N-gram precision against the reference.",
        "rouge_l": "ROUGE-L F-measure (rouge-score), longest-common-subsequence overlap with the reference.",
        "bert_score": "BERTScore F1 measure comparing semantic embedding representations of output and reference.",
        "embedding_similarity": "Cosine similarity between output and reference embeddings (via LiteLLM, any provider).",
    }

    def __init__(
        self,
        judge: Optional[BaseJudgeBackend] = None,  # unused — these metrics don't use an LLM judge
        metrics: Optional[list[str]] = None,
        embedding_model: str = "text-embedding-3-small",
        bert_score_model: str = "distilbert-base-uncased",
    ) -> None:
        self.metrics = metrics or list(self.ALL_METRICS)
        self.embedding_model = embedding_model
        self.bert_score_model = bert_score_model

    def evaluate(
        self,
        example_input: str,
        output: str,
        reference: Optional[str],
        context: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> dict[str, float]:
        if not reference:
            return {}  # nothing to compare against — not an error, just no signal

        scores: dict[str, float] = {}

        if "exact_match" in self.metrics:
            scores["exact_match"] = 1.0 if output.strip() == reference.strip() else 0.0

        if "f1" in self.metrics:
            scores["f1"] = _token_f1(output, reference)

        if "bleu" in self.metrics:
            if not _SACREBLEU_AVAILABLE:
                raise ImportError(
                    "bleu requires the 'text-metrics' extra: pip install evalkit[text-metrics]"
                )
            scores["bleu"] = sacrebleu.sentence_bleu(output, [reference]).score / 100.0

        if "rouge_l" in self.metrics or "rouge" in self.metrics:
            if not _ROUGE_AVAILABLE:
                raise ImportError(
                    "rouge requires the 'text-metrics' extra: pip install evalkit[text-metrics]"
                )
            scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
            r_score = scorer.score(reference, output)["rougeL"].fmeasure
            if "rouge_l" in self.metrics:
                scores["rouge_l"] = r_score
            if "rouge" in self.metrics:
                scores["rouge"] = r_score

        if "bert_score" in self.metrics:
            if not _BERTSCORE_AVAILABLE:
                raise ImportError(
                    "bert_score requires the 'bert-score' extra: pip install bert-score"
                )
            try:
                _, _, F1 = bert_score.score([output], [reference], model_type=self.bert_score_model, verbose=False)
                scores["bert_score"] = float(F1[0].item())
            except (OSError, MemoryError):
                scores["bert_score"] = _token_f1(output, reference)

        if "embedding_similarity" in self.metrics:
            import litellm

            response = litellm.embedding(model=self.embedding_model, input=[output, reference])
            output_vec = response["data"][0]["embedding"]
            reference_vec = response["data"][1]["embedding"]
            scores["embedding_similarity"] = _cosine_similarity(output_vec, reference_vec)

        return scores
