# Knowledge Graph RAG for Enterprise Data

Hybrid retrieval system combining a Neo4j knowledge graph with pgvector semantic
search. Routes multi-hop / relational questions to graph traversal and
single-fact / definitional questions to vector search, then merges both into
one grounded, cited answer.

**Stack:** Python · Neo4j · NVIDIA NIM / OpenRouter · pgvector · FastAPI
**Estimated build time:** 3–4 weeks (part-time)

## Why this project

Vector RAG is table stakes. This system proves understanding of where
embeddings fail (multi-hop / relational questions) and demonstrates a working
fix — measured, not asserted.

## Status

- [ ] Phase 1 — Entity/relationship extraction into Neo4j
- [ ] Phase 2 — Vector index alongside the graph
- [ ] Phase 3 — Question router (graph vs. vector vs. both)
- [ ] Phase 4 — Merge into one grounded, cited answer
- [ ] Phase 5 — Benchmark vs. plain vector RAG

See `ARCHITECTURE.md` for system design, `ONTOLOGY.md` for the entity/relationship
schema, and `TASKS.md` for the phase-by-phase build checklist.

## Corpus

**Curated arXiv papers, ~50–150, scoped to one ML subfield.**

Recommendation: retrieval-augmented generation / LLM retrieval literature.
Reasons: rich citation graph (multi-hop by construction), public and free via
arXiv API, bounded scope so extraction cost stays predictable, and it doubles
as a literature-review pass for your own research work. Swap the subfield if
you'd rather use something unrelated to keep the two projects separate.

Get papers + metadata (title, authors, abstract, references) via the arXiv API
or Semantic Scholar API — the latter gives structured citation edges directly,
which saves you from parsing PDF reference lists by hand.

## Done when

A FastAPI endpoint answers questions with validated citations, and this README
opens with a benchmark table comparing this system to a vector-only baseline,
broken out by hop count (see `TASKS.md` Phase 5).

## Resume line (fill in after benchmarking)

> Built a hybrid knowledge graph and vector RAG system over N documents; raised
> multi-hop question accuracy from X% to Y% against a vector baseline at Z ms p95.

## Known failure modes to avoid

- Open-ended ontology → ungueryable graph
- Skipping entity resolution → duplicate nodes for the same entity
- Letting the model write raw Cypher → security hole, unreproducible results
- Corpus with no real relationships → graph is pointless
