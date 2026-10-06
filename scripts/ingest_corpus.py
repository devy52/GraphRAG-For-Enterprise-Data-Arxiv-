# -*- coding: utf-8 -*-
"""
Ingest the harvested corpus into PostgreSQL (pgvector) and Neo4j.
"""
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.orchestrator import IngestionOrchestrator
from src.ingestion.models import IngestRequest


async def main():
    orchestrator = IngestionOrchestrator()
    req = IngestRequest(
        mode="load_corpus",
        populate_pgvector=True,
        populate_neo4j=True,
        reset_checkpoint=True,
    )
    print("Starting ingestion into pgvector and Neo4j...")
    started = await orchestrator.start_ingestion(req)
    if not started:
        print("Failed to start ingestion (already running).")
        return

    while orchestrator.status == "running":
        print(f"[{orchestrator.stage}] {orchestrator.progress_pct:.1f}% - {orchestrator.message}", flush=True)
        await asyncio.sleep(2.0)

    print(f"Ingestion finished with status: {orchestrator.status}")
    print(f"Final stage: {orchestrator.stage}")
    print(f"Final message: {orchestrator.message}")


if __name__ == "__main__":
    asyncio.run(main())
