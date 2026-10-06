# -*- coding: utf-8 -*-
"""
Fast parallel completion of corpus ingestion into Neo4j.
Extracts remaining chunks with controlled concurrency and batch persists to Neo4j.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.models import DocumentChunk
from src.graph.extractor import GraphExtractor
from src.graph.resolver import EntityResolver
from src.graph.writer import Neo4jWriter
from src.graph.query_engine import GraphQueryEngine

CHECKPOINT_FILE = "data/corpus/ingestion_checkpoint.json"
CHUNKS_FILE = "data/corpus/chunks.json"


def load_checkpoint() -> set:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("completed_chunk_ids", []))
    return set()


def save_checkpoint(completed: set, total_facts: int):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({"completed_chunk_ids": sorted(list(completed)), "total_facts_written": total_facts}, f, indent=2)


async def main():
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        raw_chunks = json.load(f)
    all_chunks = [DocumentChunk(**c) for c in raw_chunks]

    completed_ids = load_checkpoint()
    remaining = [c for c in all_chunks if c.chunk_id not in completed_ids]
    print(f"Total chunks: {len(all_chunks)}. Already completed: {len(completed_ids)}. Remaining: {len(remaining)}.")

    if not remaining:
        print("All chunks already ingested!")
        return

    extractor = GraphExtractor()
    resolver = EntityResolver()
    writer = Neo4jWriter()
    await writer.init_schema()

    sem = asyncio.Semaphore(6)

    async def extract_one(chunk: DocumentChunk):
        async with sem:
            facts = await extractor.extract_chunk(chunk)
            return chunk, facts

    print(f"Extracting {len(remaining)} chunks with concurrency 6...")
    tasks = [extract_one(c) for c in remaining]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    print(f"All extractions finished. Resolving entities and writing to Neo4j...")
    total_new_facts = 0
    for chunk, facts in results:
        if facts:
            resolved_entities, resolved_facts = await resolver.resolve_and_link(facts)
            if resolved_entities:
                await writer.write_entities(resolved_entities)
            if resolved_facts:
                await writer.write_facts(resolved_facts)
            total_new_facts += len(resolved_facts)
        completed_ids.add(chunk.chunk_id)

    save_checkpoint(completed_ids, total_new_facts)
    print(f"Wrote {total_new_facts} new facts to Neo4j across {len(remaining)} chunks.")

    print("Synchronizing entity registry in query engine...")
    engine = GraphQueryEngine(writer=writer, resolver=resolver)
    await engine.sync_registry_from_graph()
    await writer.close()
    print("Ingestion 100% complete!")


if __name__ == "__main__":
    asyncio.run(main())
