"""
Evalkit GraphRAG Adapter Module.

Architecture Role:
    Testing & Evaluation Integration. Bridges the external `evalkit` evaluation framework
    with the Enterprise GraphRAG system under test. Wraps query execution across FastAPI
    or the in-process async coordinator and returns structured `AdapterResponse` objects
    containing answer text, runtime retrieved context (graph facts + text chunks),
    request latency, and query metadata.

Inputs:
    - `example_input`: Natural language question string from an evalkit dataset.
    - `metadata`: Optional example metadata dictionary (e.g. hop_type, should_refuse).

Outputs:
    - `evalkit.contracts.adapter.AdapterResponse` containing:
        - `output`: Generated answer text.
        - `context`: List of facts and text chunks retrieved by the system at runtime.
        - `latency_ms`: Total query execution latency in milliseconds.
        - `metadata`: Routing decision, citations, cache hit status, and question ID.

Design Decisions:
    - Dual Execution Paths: Tries a live HTTP request to the FastAPI server first
      (`http://127.0.0.1:8000/query`). If the server is offline, transparently falls back
      to an in-process persistent event loop (`AsyncPipelineRunner`), avoiding Starlette's
      per-request loop closure and preserving database connection pools across all examples.
    - Zero Touch to Core: Completely decoupled from `src/`. Works as a standalone adapter
      for evalkit without modifying core business logic.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import httpx

# Ensure evalharness and evalkit_upgraded are accessible on sys.path
_repo_root = Path(__file__).resolve().parent
_evalharness_path = _repo_root / "evalharness"
if str(_evalharness_path) not in sys.path:
    sys.path.insert(0, str(_evalharness_path))
_evalkit_path = _repo_root / "evalkit"
if str(_evalkit_path) not in sys.path:
    sys.path.insert(0, str(_evalkit_path))
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from evalharness.contracts.adapter import AdapterResponse, BaseAdapter
except ImportError:
    from evalkit.contracts.adapter import AdapterResponse, BaseAdapter


class AsyncPipelineRunner:
    """
    Manages a persistent background event loop thread to execute async
    retrieval and synthesis queries without thread/loop closure issues.
    """

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

        async def _init_components():
            from src.api.routes import get_coordinator, get_synthesizer
            get_coordinator.cache_clear()
            get_synthesizer.cache_clear()
            coord = get_coordinator()
            synth = get_synthesizer()
            await coord.warmup()
            return coord, synth

        future = asyncio.run_coroutine_threadsafe(_init_components(), self.loop)
        self.coordinator, self.synthesizer = future.result()

    def query(self, text: str, session_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Submits query to the coordinator and synthesizer on the persistent loop.
        """
        async def _exec():
            t0 = time.time()
            ctx = await self.coordinator.retrieve(query=text, session_id=session_id)
            synth = await self.synthesizer.synthesize(context=ctx, use_cache=use_cache)
            t_total = round((time.time() - t0) * 1000.0, 2)
            latencies = dict(ctx.latency_ms)
            latencies.update(synth.latency_ms)
            latencies["total_request_ms"] = t_total
            return {
                "answer": synth.answer,
                "route_taken": synth.route.value if hasattr(synth.route, "value") else str(synth.route),
                "citations": synth.cited_chunk_ids,
                "is_grounded": synth.validation_result.is_valid,
                "from_cache": synth.from_cache,
                "graph_facts": ctx.graph_facts,
                "retrieved_chunks": [c.text for c in ctx.retrieved_chunks],
                "latency_breakdown_ms": latencies,
            }

        future = asyncio.run_coroutine_threadsafe(_exec(), self.loop)
        return future.result()


class GraphRAGAdapter(BaseAdapter):
    """
    Evaluator adapter connecting evalkit to the GraphRAG query interface.
    """

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8000/query",
        timeout_seconds: float = 120.0,
        use_cache: bool = True,
    ) -> None:
        """
        Initializes the adapter with endpoint configuration.

        Args:
            api_url: URL to the live FastAPI /query endpoint.
            timeout_seconds: Network timeout for live HTTP requests.
            use_cache: Whether query caching is permitted during evaluation.
        """
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.use_cache = use_cache
        self._async_runner: Optional[AsyncPipelineRunner] = None
        self._runner_lock = threading.Lock()

    def _get_async_runner(self) -> AsyncPipelineRunner:
        """
        Lazy-initializes the persistent AsyncPipelineRunner.
        """
        with self._runner_lock:
            if self._async_runner is None:
                self._async_runner = AsyncPipelineRunner()
            return self._async_runner

    def run(
        self, example_input: str, metadata: Optional[Dict[str, Any]] = None
    ) -> AdapterResponse:
        """
        Executes a query against the GraphRAG pipeline and packages the response.

        Args:
            example_input: The natural language question to submit.
            metadata: Dataset metadata for this question.

        Returns:
            An AdapterResponse with the answer, runtime context, and latency metrics.
        """
        payload = {
            "query": example_input,
            "use_cache": self.use_cache,
            "session_id": (metadata or {}).get("session_id", "evalkit_eval_session"),
        }

        response_data: Optional[Dict[str, Any]] = None

        # Step 1: Attempt live HTTP request to local server
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(self.api_url, json=payload)
                if resp.status_code == 200:
                    response_data = resp.json()
        except (httpx.HTTPError, Exception):
            # Server offline or unreachable; fall back to persistent in-process loop
            response_data = None

        # Step 2: Persistent in-process execution fallback
        if response_data is None:
            runner = self._get_async_runner()
            response_data = runner.query(
                text=example_input,
                session_id=payload["session_id"],
                use_cache=self.use_cache,
            )

        # Step 3: Extract answer and format runtime retrieval context
        answer_text = response_data.get("answer", "")
        graph_facts: List[str] = response_data.get("graph_facts", [])
        retrieved_chunks: List[str] = response_data.get("retrieved_chunks", [])

        # Format context passages for evalkit judge/evaluators
        runtime_context: List[str] = []
        for fact in graph_facts:
            runtime_context.append(f"[graph] {fact}")
        for chunk in retrieved_chunks:
            runtime_context.append(f"[retrieved] {chunk}")

        # Step 4: Extract latency and provenance metadata
        latencies = response_data.get("latency_breakdown_ms", {})
        latency_ms = latencies.get("total_request_ms", 0.0)

        res_metadata = {
            "route_taken": response_data.get("route_taken"),
            "citations": response_data.get("citations", []),
            "is_grounded": response_data.get("is_grounded", False),
            "from_cache": response_data.get("from_cache", False),
            "original_question_id": (metadata or {}).get("id"),
            "graph_facts_retrieved": graph_facts,
            "expected_themes": (metadata or {}).get("expected_themes"),
            "community_summary": (metadata or {}).get("community_summary"),
            "community_chunks": (metadata or {}).get("community_chunks"),
        }

        # Step 5: Return typed AdapterResponse contract
        return AdapterResponse(
            output=answer_text,
            context=runtime_context,
            latency_ms=latency_ms,
            metadata=res_metadata,
        )
