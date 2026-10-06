"""Example of a real (non-static) adapter for your own RAG pipeline.

Point config.yaml's `adapter` at "my_adapter:MyRagAdapter" (run evalkit from
this directory, or make sure it's on your PYTHONPATH) instead of "static" to
use this. No changes to evalkit itself are needed.
"""

from __future__ import annotations

from typing import Any, Optional

from evalkit.contracts.adapter import BaseAdapter


class MyRagAdapter(BaseAdapter):
    def __init__(self, api_url: str = "http://localhost:8000/query") -> None:
        self.api_url = api_url

    def run(self, example_input: str, metadata: Optional[dict[str, Any]] = None) -> str:
        # Replace with a real call into your pipeline, e.g.:
        #   import requests
        #   return requests.post(self.api_url, json={"query": example_input}).json()["answer"]
        raise NotImplementedError("Wire this up to your actual RAG endpoint.")
