# -*- coding: utf-8 -*-
"""
Harvest a fresh, modern corpus of Agentic RAG and GraphRAG research papers (2023-2025).
"""
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.collector import PaperCollector
from src.ingestion.chunker import DocumentChunker
import json


async def main():
    collector = PaperCollector()
    query = "all:GraphRAG OR all:\"graph retrieval-augmented generation\" OR all:\"agentic rag\""
    print(f"Querying arXiv for modern GraphRAG / Agentic RAG papers...")
    papers = await collector.collect_corpus(
        query=query,
        limit=30,
        output_path="data/corpus/papers.json",
    )
    print(f"Successfully harvested {len(papers)} papers.")
    for idx, p in enumerate(papers, 1):
        print(f"[{idx}] {p.arxiv_id} ({p.published_year}): {p.title}")

    # Chunk papers
    chunker = DocumentChunker()
    all_chunks = []
    for p in papers:
        chunks = chunker.chunk_paper(p)
        all_chunks.extend(chunks)

    os.makedirs("data/corpus", exist_ok=True)
    with open("data/corpus/chunks.json", "w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in all_chunks], f, indent=2)

    print(f"Generated {len(all_chunks)} boundary-aligned chunks in data/corpus/chunks.json.")


if __name__ == "__main__":
    asyncio.run(main())
