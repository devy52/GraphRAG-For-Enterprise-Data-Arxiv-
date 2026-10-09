[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md) | [Scorecard](BENCHMARK_SCORECARD.md)
---

# System Sequence Flows & Interaction Diagrams (FLOWS)

## 1. Corpus Ingestion & Knowledge Graph Extraction Flow

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Data Pipeline / Admin
    participant Collector as PaperCollector
    participant Chunker as DocumentChunker
    participant Extractor as GraphExtractor
    participant Resolver as EntityResolver
    participant NeoWriter as Neo4jWriter
    participant VectorStore as VectorStore

    Admin->>Collector: fetch_papers(topic="RAG", limit=100)
    Collector->>Collector: Polite Rate Limit (3s delay)
    Collector-->>Admin: List[Paper]

    loop For each Paper
        Admin->>Chunker: chunk_paper(paper)
        Chunker-->>Admin: List[DocumentChunk] (SHA-256 IDs)

        par Vector Ingestion
            Admin->>VectorStore: insert_chunks(chunks)
            VectorStore->>VectorStore: Generate Embeddings (batch=32)
            VectorStore->>VectorStore: Upsert into PostgreSQL (HNSW index)
        and Knowledge Graph Ingestion
            Admin->>Extractor: extract_from_chunks(chunks)
            Extractor->>Extractor: Check Extraction Cache
            Extractor-->>Admin: List[ExtractedFact]
            Admin->>Resolver: resolve_facts(facts)
            Resolver->>Resolver: Normalize + Token Jaccard + Cosine (>=0.88)
            Resolver-->>Admin: List[ExtractedFact] (canonical)
            Admin->>NeoWriter: write_facts(resolved_facts)
            NeoWriter->>NeoWriter: Idempotent MERGE + source_chunk_id
        end
    end
```

---

## 2. Coordinated Query Retrieval Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Client Application / User
    participant API as FastAPI /query
    participant Coord as RetrievalCoordinator
    participant Memory as SessionMemory
    participant Router as RouteClassifier
    participant GraphEng as GraphQueryEngine
    participant VecStore as VectorStore

    User->>API: POST /query {"query": "Explain its contrastive loss", "session_id": "s1"}
    API->>Coord: retrieve(query, session_id)
    Coord->>Memory: resolve_coreference(query)
    Memory-->>Coord: "Explain Dense Passage Retrieval contrastive loss"

    Coord->>Router: classify(resolved_query)
    Router->>Router: Score Intent (structural vs semantic)
    alt Confidence < 0.70
        Router-->>Coord: RouteDecision.BOTH (escalated)
    else Confidence >= 0.70
        Router-->>Coord: RouteDecision (GRAPH | VECTOR | BOTH)
    end

    par Graph Execution (if GRAPH or BOTH)
        Coord->>GraphEng: query(resolved_query)
        GraphEng->>GraphEng: Select Cypher Template + Bind Params
        GraphEng->>GraphEng: Execute Neo4j Traversal
        GraphEng-->>Coord: GraphQueryResult (facts + source_chunk_ids)
    and Vector Execution (if VECTOR or BOTH)
        Coord->>VecStore: similarity_search(resolved_query, top_k=5)
        VecStore->>VecStore: Cosine Distance Search (<=>)
        VecStore-->>Coord: List[VectorSearchResult]
    end

    Coord->>Memory: add_user_turn(resolved_query, entities)
    Coord-->>API: RetrievalContext
```

---

## 3. Answer Synthesis & Citation Hard-Gate Validation Loop

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI /query
    participant Synth as AnswerSynthesizer
    participant Cache as QueryResponseCache
    participant LLM as OpenRouter / NVIDIA Gateway
    participant Val as CitationValidator

    API->>Synth: synthesize(RetrievalContext, use_cache=True)
    Synth->>Cache: get(query_hash)
    alt Cache Hit
        Cache-->>Synth: Cached SynthesizedAnswer
        Synth-->>API: Return Cached Answer (latency < 1ms)
    else Cache Miss
        Synth->>Synth: assemble_context (partition [graph] & [retrieved])

        loop Max 2 Attempts
            Synth->>LLM: Generate Answer with [chunk_id] citations
            LLM-->>Synth: Generated Answer Text
            Synth->>Val: validate(text, allowed_chunk_ids)
            alt All Citations Valid
                Val-->>Synth: is_valid = True
                Note over Synth: Break retry loop
            else Hallucinated Citations Detected
                Val-->>Synth: is_valid = False + Error Message
                Synth->>Synth: Append Diagnostic Feedback to Prompt
            end
        end

        Synth->>Cache: set(query_hash, answer)
        Synth-->>API: SynthesizedAnswer (is_grounded = True)
    end
```

---

## 4. System Health Check Flow

```mermaid
sequenceDiagram
    autonumber
    actor Monitor as Kubernetes / Health Monitor
    participant API as FastAPI /health
    participant Neo4j as Neo4j Driver
    participant Postgres as SQLAlchemy Engine

    Monitor->>API: GET /health
    par Check Graph DB
        API->>Neo4j: verify_connectivity()
        Neo4j-->>API: Connection OK
    and Check Vector DB
        API->>Postgres: SELECT 1;
        Postgres-->>API: Connection OK
    end
    API-->>Monitor: 200 OK {"status": "healthy", "neo4j_connected": true, "postgres_connected": true}
```

---

## 5. Material 3 Interactive Query & Graph Exploration Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User in Browser
    participant UI as M3 Web Interface (HTML/CSS/JS)
    participant API as FastAPI Router
    participant Coord as RetrievalCoordinator
    participant Synth as AnswerSynthesizer
    participant GraphEng as GraphQueryEngine

    Note over User, UI: Navigation Rail: Chat Workspace
    User->>UI: Submit natural language query
    UI->>API: POST /query {"query": "...", "use_cache": true}
    API->>Coord: retrieve(query)
    Coord-->>API: RetrievalContext (route, graph_facts, chunks)
    API->>Synth: synthesize(context)
    Synth-->>API: SynthesizedAnswer (answer, citations, grounded)
    API-->>UI: 200 OK QueryResponse
    UI->>UI: Render Answer + Route Badge + Latency Breakdown
    User->>UI: Click citation [chunk_id]
    UI->>UI: Open M3 modal showing raw chunk passage & metadata

    Note over User, UI: Navigation Rail: Neo4j Topology
    User->>UI: Switch to Graph Explorer tab
    UI->>API: GET /graph/subgraph?limit=150
    API->>GraphEng: Fetch active nodes & relationships
    GraphEng-->>API: Subgraph data (nodes, edges)
    API-->>UI: 200 OK Subgraph JSON
    UI->>UI: Render 60 FPS Force-Directed Canvas with ontology colors
    User->>UI: Click on graph node (e.g. 'RAG-Sequence')
    UI->>UI: Display node properties, aliases, and connected relationships
```

---

## 6. Customizable Corpus Ingestion & Live Progress Tracking Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User in Browser
    participant UI as M3 Ingestion Dialog
    participant API as FastAPI Routes
    participant Orch as IngestionOrchestrator
    participant ArXiv as arXiv API / Corpus
    participant Chunker as TextChunker
    participant Vec as VectorStore (pgvector)
    participant Ext as GraphExtractor (LLM)
    participant Res as EntityResolver
    participant Neo as GraphWriter (Neo4j)

    User->>UI: Open Ingestion Dialog & Configure (Mode, Query, Limit, Toggles)
    User->>UI: Click "Start Ingestion"
    UI->>API: POST /ingest {mode, query, paper_limit, chunk_limit, populate_neo4j, populate_pgvector}
    API->>Orch: start_ingestion(request)
    Orch-->>API: Task initiated (status="running")
    API-->>UI: 202 Accepted {"status": "running", "stage": "harvesting"}

    par Async Ingestion Worker
        alt Harvest New Papers
            Orch->>ArXiv: Harvest papers with polite rate limits
            ArXiv-->>Orch: Raw paper metadata & abstracts
            Orch->>Chunker: Split documents into boundary-aligned chunks
            Chunker-->>Orch: DocumentChunk collection
        end
        opt Populate pgvector
            Orch->>Vec: Generate embeddings & insert chunks into pgvector
            Vec-->>Orch: Embeddings indexed
        end
        opt Populate Neo4j
            loop For each chunk (up to chunk_limit)
                Orch->>Ext: Extract fact triples via schema-validated LLM
                Ext-->>Orch: ExtractedFact triples
                Orch->>Res: Resolve entities & normalize aliases
                Res-->>Orch: Resolved entities & edges
                Orch->>Neo: Idempotent MERGE into Neo4j
                Neo-->>Orch: Graph updated
            end
        end
        Orch->>Orch: Set status="completed"
    and UI Progress Polling
        loop Every 1.5s until completed or failed
            UI->>API: GET /ingest/status
            API->>Orch: get_status()
            Orch-->>API: IngestStatusResponse (progress_pct, stage, logs)
            API-->>UI: 200 OK Status JSON
            UI->>UI: Update M3 linear progress bar, stage badge & log console
        end
    end
    UI->>UI: Show completion badge & refresh Graph Explorer canvas
```

---

## 7. Integrated Bounded LangGraph Evidence Refinement Flow (ADR 070)

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client / FastAPI Route / Benchmark
    participant Coord as RetrievalCoordinator (src/router/coordinator.py)
    participant Refiner as EvidenceRefiner (src/router/refiner.py)
    participant Gap as Heuristic Gap Detector (<1ms)
    participant StateGraph as LangGraph Refinement StateGraph
    participant Neo4j as Neo4j Graph (Ego-Neighborhood)
    participant Vec as pgvector (Doc-Filtered)
    participant Synth as AnswerSynthesizer (src/synthesis/)
    participant Val as CitationValidator (src/synthesis/)

    Client->>Coord: retrieve(question, enable_evidence_refinement=True)
    Coord->>Coord: Steps 1-3e: Intent Routing, Graph Traversal & Passage Hydration
    
    Coord->>Refiner: refine(question, initial_graph_facts, initial_chunks)
    Refiner->>Gap: detect_evidence_gap(question, facts, chunks)
    Gap->>Gap: Check Canonical Entity Registry & Target Paper Catalog

    alt No Gap Detected (Fast Path: ~54% of queries)
        Gap-->>Refiner: has_gap=False
        Refiner-->>Coord: refinement_activated=False (0 extra items)
        Note over Coord: Bypasses LangGraph StateGraph completely
    else Gap Detected (Refined Path: ~46% of queries)
        Gap-->>Refiner: has_gap=True (missing_entities, missing_docs)
        Refiner->>StateGraph: ainvoke(RefinementState)

        StateGraph->>StateGraph: Node 1: isolate_gap_node
        StateGraph->>Neo4j: Node 2: execute_query(EGO_NEIGHBORHOOD, missing_entity)
        Neo4j-->>StateGraph: Refined graph statements
        StateGraph->>Vec: Node 2: similarity_search(filter_doc_ids=missing_docs)
        Vec-->>StateGraph: Refined vector chunks

        StateGraph->>StateGraph: Node 3: merge_evidence_node (Deduplicate & Budget Caps)
        StateGraph-->>Refiner: Refinement Output (<=3 facts, <=2 chunks, latencies)
        Refiner-->>Coord: Refinement Output

        Coord->>Coord: Merge into RetrievalContext & Register cited_chunk_ids
    end

    Coord-->>Client: RetrievalContext (facts, chunks, cited_chunk_ids, refinement telemetry)
    Client->>Synth: synthesize(RetrievalContext)
    Synth->>Val: validate(answer, cited_chunk_ids)
    Val-->>Synth: is_valid=True (0% invalid citations)
    Synth-->>Client: QueryResponse / SynthesizedAnswer
```

