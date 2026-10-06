"""
LLM Entity & Relationship Extraction Engine.

Architecture Role:
    Part of Phase 2 (Knowledge Graph Ingestion). Translates unstructured text chunks into
    strict, ontology-compliant knowledge graph triples. These extracted triples are later
    passed to `EntityResolver` for deduplication and then persisted to Neo4j by `Neo4jWriter`.

Inputs:
    - `DocumentChunk` instances from Phase 1.
    - System prompt defining strict entity types and relation types from `Docs/ONTOLOGY.md`.

Outputs:
    - List of validated `ExtractedFact` domain models with source/target entities, relationship types,
      confidence scores, and `source_chunk_id` foreign keys.
    - Persistent extraction cache file (`data/cache/extraction_cache.json`).

Design Decisions:
    - Zero-Temperature Determinism: Uses temperature=0.0 to maximize reproducible extractions.
    - Local SHA-256 Cache: Skips LLM calls for identical text chunks to prevent redundant API bills.
    - Feedback Self-Correction Loop: If Pydantic or JSON parsing fails, the error message is fed back
      to the LLM in a multi-turn conversation for self-healing up to `MAX_VALIDATION_RETRIES`.
    - Chunk Traceability: Injects `source_chunk_id` onto every fact so graph traversals can link
      directly back to original text passages for grounded citations.
"""

import json
import os
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.models import EntityType, ExtractedFact, ExtractionPayload, RelationType
from src.ingestion.models import DocumentChunk

logger = setup_logger(name="graph.extractor")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
MAX_VALIDATION_RETRIES = 2     # Maximum self-healing correction attempts on schema failure
TEMPERATURE = 0.0              # Deterministic zero temperature
CACHE_FILE_PATH = "data/cache/extraction_cache.json"

# Strict Ontology Extraction System Prompt
EXTRACTION_SYSTEM_PROMPT = """You are a knowledge graph extraction engine specialized in scientific and technical enterprise documents.
Your task is to extract factual relationships from the provided text according to a STRICT ONTOLOGY.

### ALLOWED ENTITY TYPES:
- Paper: A single publication title or named document.
- Author: A person who wrote or contributed to a publication.
- Institution: An academic or corporate organization (e.g. 'Meta AI', 'Stanford University').
- Venue: A conference, journal, or preprint archive (e.g. 'NeurIPS', 'arXiv').
- Topic: A high-level technical subject or research domain (e.g. 'dense retrieval', 'RAG').
- Dataset: A benchmark or dataset used in experiments (e.g. 'Natural Questions', 'MS MARCO').
- Method: A named model, algorithm, or architecture (e.g. 'RAG-Sequence', 'DPR', 'BM25').

### ALLOWED RELATIONSHIP TYPES:
- CITES (Paper -> Paper): Citation between publications.
- AUTHORED_BY (Paper -> Author): Paper authorship.
- AFFILIATED_WITH (Author -> Institution): Author's organizational affiliation.
- PUBLISHED_IN (Paper -> Venue): Publication venue.
- HAS_TOPIC (Paper -> Topic): Subject classification.
- USES_DATASET (Paper -> Dataset): Evaluated or trained on dataset.
- USES_METHOD (Paper -> Method): Paper applies or builds with method.
- EXTENDS (Method -> Method): Technique builds upon or enhances prior method.
- COMPARED_WITH (Method -> Method): Methods directly benchmarked against each other.

### OUTPUT FORMAT:
You MUST respond with valid JSON matching the following schema:
{
  "facts": [
    {
      "source_name": "Exact canonical entity name",
      "source_type": "One of allowed entity types",
      "relation": "One of allowed relationship types",
      "target_name": "Exact canonical target entity name",
      "target_type": "One of allowed entity types",
      "confidence": 1.0
    }
  ]
}

DO NOT invent new entity types or relation types outside the allowed ontology.
If no explicit relationships exist in the text, return {"facts": []}.
"""


class GraphExtractor:
    """
    Executes schema-validated LLM extraction of knowledge graph facts from text passages.
    """

    def __init__(self, cache_path: str = CACHE_FILE_PATH) -> None:
        self.settings = get_settings()
        self.cache_path = cache_path
        self.client = AsyncOpenAI(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key or "sk-dummy-key-for-test",
        )
        self.cache: Dict[str, List[dict]] = self._load_cache()

    def _load_cache(self) -> Dict[str, List[dict]]:
        """Loads cached extraction facts from disk if available."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("Failed to load extraction cache: %s. Initializing empty cache.", exc)
        return {}

    def _save_cache(self) -> None:
        """Persists updated extraction cache to disk atomically."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("Failed to save extraction cache: %s", exc)

    async def extract_chunk(self, chunk: DocumentChunk) -> List[ExtractedFact]:
        """
        Extracts ontology-constrained facts from a single DocumentChunk.

        Workflow:
        1. Cache Check: Return instantly if chunk.sha256_hash exists in local cache.
        2. Prompt Assembly: Format passage text with title and section context.
        3. LLM Request: Call OpenAI-compatible endpoint with JSON mode.
        4. Validation & Attribution: Inject source_chunk_id and validate Pydantic types.
        5. Self-Correction Loop: Retry with error feedback if schema validation fails.
        6. Cache Update: Persist validated facts to disk.
        """
        # ----------------------------------------------------------------------
        # Step 1: Check Local SHA-256 Cache
        # ----------------------------------------------------------------------
        if chunk.sha256_hash in self.cache:
            logger.debug("Extraction cache hit for chunk %s", chunk.chunk_id)
            cached_data = self.cache[chunk.sha256_hash]
            return [ExtractedFact(**fact) for fact in cached_data]

        # ----------------------------------------------------------------------
        # Step 2: Build Structured Prompt
        # ----------------------------------------------------------------------
        user_prompt = (
            f"Document Title: {chunk.paper_title}\n"
            f"Section: {chunk.section_path}\n"
            f"Chunk ID: {chunk.chunk_id}\n\n"
            f"Passage Text:\n\"\"\"\n{chunk.text}\n\"\"\""
        )

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # ----------------------------------------------------------------------
        # Step 3: Execute LLM Extraction with Self-Correction Retries
        # ----------------------------------------------------------------------
        for attempt in range(MAX_VALIDATION_RETRIES + 1):
            raw_content = "{}"
            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.extraction_model,
                    messages=messages,
                    temperature=TEMPERATURE,
                    response_format={"type": "json_object"},
                )
                raw_content = response.choices[0].message.content or "{}"
                parsed_json = json.loads(raw_content)

                # Step 4: Inject source_chunk_id foreign key for ground truth attribution
                facts_data = parsed_json.get("facts", [])
                rel_normalization = {
                    "USE_METHOD": "USES_METHOD",
                    "USE_DATASET": "USES_DATASET",
                    "EXTEND": "EXTENDS",
                    "COMPARE_WITH": "COMPARED_WITH",
                    "AUTHOR_BY": "AUTHORED_BY",
                    "AFFILIATE_WITH": "AFFILIATED_WITH",
                    "PUBLISH_IN": "PUBLISHED_IN",
                    "TOPIC": "HAS_TOPIC",
                }
                for fact in facts_data:
                    fact["source_chunk_id"] = chunk.chunk_id
                    rel = str(fact.get("relation", "")).strip().upper()
                    if rel in rel_normalization:
                        fact["relation"] = rel_normalization[rel]
                    elif rel:
                        fact["relation"] = rel
                    for type_key in ("source_type", "target_type"):
                        val = str(fact.get(type_key, "")).strip().title()
                        if val in {"Paper", "Author", "Institution", "Venue", "Topic", "Dataset", "Method"}:
                            fact[type_key] = val

                # Step 5: Validate against strict Pydantic ontology schema
                payload = ExtractionPayload(facts=facts_data)

                # Step 6: Update cache and save to disk
                self.cache[chunk.sha256_hash] = [f.model_dump() for f in payload.facts]
                self._save_cache()

                logger.info("Extracted %d facts from chunk %s", len(payload.facts), chunk.chunk_id)
                return payload.facts

            except (json.JSONDecodeError, ValidationError) as err:
                logger.warning(
                    "Extraction schema validation failed on attempt %d/%d for chunk %s: %s",
                    attempt + 1,
                    MAX_VALIDATION_RETRIES + 1,
                    chunk.chunk_id,
                    err,
                )
                # Self-healing feedback loop: pass validation error back to LLM for correction
                if attempt < MAX_VALIDATION_RETRIES:
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Schema validation failed: {str(err)}. "
                            "Return strictly valid JSON matching the schema with allowed entity and relation types only."
                        ),
                    })
                else:
                    logger.error("Exhausted extraction retries for chunk %s. Returning empty fact list.", chunk.chunk_id)
                    return []
            except Exception as exc:
                logger.error("Unexpected error during LLM extraction for chunk %s: %s", chunk.chunk_id, exc)
                return []

        return []

    async def extract_corpus(self, chunks: List[DocumentChunk]) -> List[ExtractedFact]:
        """
        Processes a collection of chunks sequentially, logging progress.

        Args:
            chunks: List of DocumentChunk models to extract facts from.

        Returns:
            Flat list of all extracted ExtractedFact models.
        """
        all_facts: List[ExtractedFact] = []
        for i, chunk in enumerate(chunks):
            logger.info("Processing chunk [%d/%d]: %s", i + 1, len(chunks), chunk.chunk_id)
            facts = await self.extract_chunk(chunk)
            all_facts.extend(facts)
        return all_facts
