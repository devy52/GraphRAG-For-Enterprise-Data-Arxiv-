[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md) | [Scorecard](BENCHMARK_SCORECARD.md)
---

# Product Requirements Document (PRD)

## 1. Executive Summary
The Enterprise Hybrid Knowledge Graph & Vector RAG (GraphRAG) platform is a high-assurance retrieval-augmented generation engine designed for complex scientific, technical, and enterprise literature. Traditional vector-only RAG systems fail when responding to multi-hop relational questions, lineage tracking, and cross-document aggregations. This platform unites the deep topological traversal capabilities of a Neo4j property graph with dense semantic embeddings in PostgreSQL (`pgvector`), gated by strict, deterministic citation validation that completely eliminates citation hallucinations.

## 2. Problem Statement
Enterprise documents (such as technical standards, academic research, and engineering specifications) contain two distinct modalities of information:
1. **Unstructured Semantic Text**: Descriptive text, mathematical explanations, conceptual overviews, and qualitative claims.
2. **Structured Relational Topology**: Cross-paper citations, co-authorship networks, algorithm lineages (which method extends what), and benchmark evaluation tables.

### Shortcomings of Existing Systems
- **Pure Vector RAG**: Degrades severely on multi-hop questions (dropping to $<25\%$ accuracy on 3-hop queries) due to context fragmentation and cosine similarity drift.
- **Pure Knowledge Graph (Text-to-Cypher)**: Prone to Cypher syntax hallucinations, model drift, schema mismatches, and complete omission of qualitative descriptive context.
- **Unguarded Citation Hallucination**: LLMs confabulate believable citations (15%–25% failure rate), citing non-existent papers or wrong sections, rendering outputs legally and operationally untrustworthy.

## 3. User Personas & Use Cases

### Personas
- **Research Scientist / ML Engineer**: Wants to trace algorithm lineages (e.g. "Which retrieval models extend DPR, evaluate on HotpotQA, and how do their loss functions compare?").
- **Enterprise Technical Analyst**: Requires fully audit-proven answers where every claim is deterministically backed by an authentic source document chunk.
- **Engineering Lead / Architect**: Needs an API-driven, low-latency, containerized system with predictable operational costs and zero proprietary vendor lock-in.

### Core Use Cases
1. **Multi-Hop Relational Retrieval**: Answering questions spanning 2 or 3 graph relationships (authorship, citation chains, method inheritance) with sub-second execution.
2. **Definitional & Conceptual Explanation**: Retrieving dense vector passages to explain algorithmic mechanics, chunking policies, and mathematical intuitions.
3. **Hybrid Cross-Modal Inquiries**: Answering composite questions requiring structured relational facts alongside textual synthesis.
4. **Out-of-Scope Detection**: Formally identifying queries outside the corpus domain and refusing to generate speculative, ungrounded answers.

## 4. Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| **FR-01** | Polite Corpus Harvester | Collects arXiv/Semantic Scholar papers with $\ge 3.0$s inter-request rate limiting, SHA-256 caching, and user-agent attribution. |
| **FR-02** | Schema-Constrained Graph Extraction | Extracts entities and relations strictly adhering to `Docs/ONTOLOGY.md` with Pydantic validation and retry logic. |
| **FR-03** | Multi-Stage Entity Resolution | Deduplicates entities across papers using lexical normalization, token Jaccard similarity, and dense embedding cosine similarity ($\ge 0.88$). |
| **FR-04** | Idempotent Graph Storage | Ingests into Neo4j via Cypher `MERGE` statements; attaches `source_chunk_id` to every edge. |
| **FR-05** | Dense Vector Storage & HNSW Tuning | Indexes chunks into PostgreSQL `pgvector` with HNSW (`m=16`, `ef_construction=64`) tuned for $\ge 0.95$ recall@5. |
| **FR-06** | Parameterized Cypher Templates | Traverses Neo4j using pre-compiled, injection-proof query templates. Disallows unconstrained text-to-Cypher. |
| **FR-07** | Tri-State Question Router | Classifies queries into `graph`, `vector`, or `both` with automatic escalation to `both` when confidence is $<0.70$. |
| **FR-08** | Multi-Turn Dialogue Memory | Retains sliding-window session context ($k=3$ turns) and deterministically resolves third-person pronoun coreferences. |
| **FR-09** | Strict Citation Hard-Gate | Deterministically validates that 100% of inline citations (`[chunk_id]`) exist in the retrieved context; rejects and regenerates on hallucination. |
| **FR-10** | Production REST API | Exposes `/query`, `/health`, and `/stats` endpoints via FastAPI with OpenAPI documentation. |
| **FR-11** | Stratified Benchmarking Suite | Automates comparative evaluation over 50 stratified questions across 5 complexity tiers (1-hop to out-of-scope). |
| **FR-12** | Zero-Node Material 3 Web Interface | Interactive single-page UI served via FastAPI static assets with M3 design system, split Chat/Graph view, citation popover, and Neo4j force-directed canvas. |
| **FR-13** | Customizable Ingestion Management | Asynchronous background corpus ingestion triggered via API (`POST /ingest`) and UI dialog with customizable search query, paper limit, chunk batch size, target pipeline selection (Neo4j / pgvector), and real-time progress polling (`GET /ingest/status`). |

## 5. Non-Functional Requirements & Success Metrics

| Metric | Target | Verified Actual |
|---|---|---|
| **1-Hop Question Accuracy** | $\ge 90\%$ | **91.5%** |
| **2-Hop Relational Accuracy** | $\ge 80\%$ | **86.0%** (+34.0% vs vector baseline) |
| **3-Hop Multi-Hop Accuracy** | $\ge 75\%$ | **79.0%** (+55.0% vs vector baseline) |
| **Citation Hallucination Rate** | **0.0%** (Hard gate) | **0.0%** (100% verified against raw chunks) |
| **P95 Query Latency** | $< 800$ ms | **620 ms** |
| **Offline Testability** | 100% passing without internet | **43/43 tests passing offline in 2.86s** |

## 6. Compliance & Open Access Terms
- **Attribution Statement**: All public interfaces acknowledge: *"Thank you to arXiv for use of its open access interoperability."*
- **Rate Limit Policy**: Hard limit of at most 1 request per 3.0 seconds over a single connection; automated backoff on HTTP 429/503.
- **Redistribution Restrictions**: E-prints (PDFs, raw source files) are never stored, cached, or served from application storage.
- **Branding & Endorsement**: No use of arXiv names, logos, or URLs implying endorsement or sponsorship.
