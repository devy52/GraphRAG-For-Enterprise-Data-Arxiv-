[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md) | [Scorecard](BENCHMARK_SCORECARD.md)
---

# Ontology

Fixed before any extraction code is written. An open-ended "extract all
entities" prompt produces a graph nobody can query — this file is what
prevents that.

## Entity types (target: 5–10)

Draft for an arXiv/RAG-subfield corpus — adjust once you're looking at real data:

| Entity type | Description | Example |
|---|---|---|
| Paper | A single publication | "Retrieval-Augmented Generation for..." |
| Author | A person who wrote a paper | "Patrick Lewis" |
| Institution | Author affiliation | "Meta AI" |
| Venue | Conference/journal/preprint server | "NeurIPS 2020" |
| Topic | A subfield/keyword tag | "dense retrieval" |
| Dataset | A benchmark used in experiments | "Natural Questions" |
| Method | A named technique/model/architecture | "RAG-Sequence" |

## Relationship types (target: 8–15)

| Relationship type | Source entity | Target entity | Description |
|---|---|---|---|
| CITES | Paper | Paper | Standard citation |
| AUTHORED_BY | Paper | Author | Authorship |
| AFFILIATED_WITH | Author | Institution | Author's org |
| PUBLISHED_IN | Paper | Venue | Where it appeared |
| HAS_TOPIC | Paper | Topic | Subject tagging |
| USES_DATASET | Paper | Dataset | Evaluated on |
| USES_METHOD | Paper | Method | Technique applied |
| EXTENDS | Method | Method | Builds on prior technique |
| COMPARED_WITH | Method | Method | Benchmarked against, per paper |

## Extraction schema (per extracted fact)

```json
{
  "entity_type": "",
  "canonical_name": "",
  "relationship_type": "",
  "target_entity": "",
  "source_chunk_id": "",
  "confidence": 0.0
}
```

## Entity resolution rules

- Normalize casing/whitespace/punctuation first
- Compare candidates via embedding similarity; threshold = _TBD_ (tune against
  a small labeled set of known duplicates)
- Store resolved aliases on the canonical node, e.g. `aliases: ["Acme Corp", "ACME"]`

## Cypher query templates (filled in during Phase 3)

Keep every graph query the model can trigger as a named, parameterized template
here. The model fills parameters; it never writes Cypher directly.

| Template name | Use case | Cypher | Parameters |
|---|---|---|---|
| _TBD_ | | | |
