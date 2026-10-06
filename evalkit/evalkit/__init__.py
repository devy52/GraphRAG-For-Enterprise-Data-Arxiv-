from evalkit.core.registry import registry

from evalkit.evaluators.rag import RagEvaluator
from evalkit.evaluators.generic import GenericEvaluator
from evalkit.evaluators.text_similarity import TextSimilarityEvaluator
from evalkit.evaluators.retrieval import RetrievalEvaluator
from evalkit.evaluators.graph import GraphEvaluator
from evalkit.judges.litellm_judge import LiteLLMJudge
from evalkit.judges.dummy_judge import DummyJudgeBackend

from evalkit.adapters.static import StaticAdapter

from evalkit.core.report import JSONReporter, HTMLReporter, MarkdownReporter

registry.register_evaluator("rag", RagEvaluator)
registry.register_evaluator("generic", GenericEvaluator)
registry.register_evaluator("text_similarity", TextSimilarityEvaluator)
registry.register_evaluator("retrieval", RetrievalEvaluator)
registry.register_evaluator("graph", GraphEvaluator)

from evalkit.evaluators import ragas_backed as _ragas_backed

if _ragas_backed._RAGAS_AVAILABLE:
    registry.register_evaluator("ragas", _ragas_backed.RagasEvaluator)

registry.register_judge_backend("litellm", LiteLLMJudge)
registry.register_judge_backend("dummy", DummyJudgeBackend)

registry.register_adapter("static", StaticAdapter)

registry.register_reporter("json", JSONReporter)
registry.register_reporter("html", HTMLReporter)
registry.register_reporter("markdown", MarkdownReporter)

__all__ = ["registry"]
__version__ = "0.1.0"
