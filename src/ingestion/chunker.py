"""
Document Chunker Module.

Architecture Role:
    Part of Phase 1 (Ingestion). Serves as the universal bridge between raw unstructured
    academic documents (`Paper` models) and the dual retrieval backends:
    1. Knowledge Graph Extraction (Phase 2): LLM processes text chunks to extract facts.
    2. Dense Vector Indexing (Phase 3): Chunks are embedded and stored in PostgreSQL pgvector.

Inputs:
    - List of `Paper` domain models (with abstract or full text).
    - Chunking hyperparameters (`chunk_size=800`, `chunk_overlap=100`).

Outputs:
    - List of `DocumentChunk` domain models, each containing:
        * Deterministic `chunk_id` (`chunk_{sanitized_paper_id}_{index:03d}`)
        * `sha256_hash` of text content for idempotent LLM extraction caching
        * Structural metadata (`paper_title`, `section_path`, `chunk_index`)
    - Serialized JSON chunks file (e.g., `data/corpus/chunks.json`).

Design Decisions:
    - Boundary-Aware Splitting: Avoids arbitrary token cuts by walking backwards from the target
      window to find paragraph (`\n\n`), newline (`\n`), or sentence boundaries (`. `).
    - Idempotency & Caching: Every chunk's SHA-256 hash allows downstream LLM extraction to
      bypass already-processed chunks, preventing redundant LLM API costs.
"""

import hashlib
import json
import os
import re
from typing import List, Optional

from src.core.logging import setup_logger
from src.ingestion.models import DocumentChunk, Paper

logger = setup_logger(name="ingestion.chunker")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
DEFAULT_CHUNK_SIZE = 800       # Target characters per chunk (~150-200 words)
DEFAULT_CHUNK_OVERLAP = 100    # Overlap characters between consecutive chunks to maintain context
MIN_CHUNK_LENGTH = 50          # Discard residual fragments shorter than this threshold


class DocumentChunker:
    """
    Recursively slices raw text into metadata-rich, boundary-aligned DocumentChunks.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def compute_sha256(text: str) -> str:
        """
        Computes a deterministic SHA-256 hexadecimal digest for raw text content.
        Used as the primary key in extraction cache lookups.
        """
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _sanitize_id(identifier: str) -> str:
        """
        Sanitizes paper IDs for safe usage in chunk IDs and file systems.
        Replaces colons, slashes, and special characters with underscores.
        """
        return re.sub(r"[^a-zA-Z0-9_\-]", "_", identifier)

    def _split_text_recursive(self, text: str) -> List[str]:
        """
        Recursively splits text on natural linguistic boundaries (paragraphs -> sentences -> words).

        Algorithm:
        1. If text is already smaller than `chunk_size`, return immediately.
        2. Slide a window of size `chunk_size` with step size `chunk_size - chunk_overlap`.
        3. Within the overlap zone, search backwards for the cleanest natural separator
           (`\\n\\n` -> `\\n` -> `. ` -> `' '`) to avoid truncating mid-sentence.
        """
        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text] if len(text) >= MIN_CHUNK_LENGTH else []

        chunks: List[str] = []
        # Natural hierarchy of separators from largest semantic block to smallest
        separators = ["\n\n", "\n", ". ", " "]
        
        # Step size accounts for overlap to guarantee contiguous contextual coverage
        step = self.chunk_size - self.chunk_overlap
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # If not at the very end of text, locate natural boundary near 'end'
            if end < len(text):
                best_cut = end
                for sep in separators:
                    # Search backwards within the overlap window for separator
                    candidate = text.rfind(sep, start + self.chunk_overlap, end)
                    if candidate != -1:
                        best_cut = candidate + len(sep)
                        break
                end = best_cut

            chunk_content = text[start:end].strip()
            # Only record non-trivial chunks that meet the minimum length threshold
            if len(chunk_content) >= MIN_CHUNK_LENGTH:
                chunks.append(chunk_content)

            if end >= len(text):
                break
            start += step

        return chunks

    def chunk_paper(self, paper: Paper) -> List[DocumentChunk]:
        """
        Transforms a single paper into structured, metadata-tracked DocumentChunk models.

        Args:
            paper: Validated Paper instance with abstract or full text.

        Returns:
            List of DocumentChunk instances.
        """
        # Step 1: Select source text (prefer full text over abstract if available)
        raw_text = paper.full_text if paper.full_text else paper.abstract
        if not raw_text or len(raw_text.strip()) < MIN_CHUNK_LENGTH:
            return []

        # Step 2: Sanitize paper identifier for deterministic naming
        clean_paper_id = self._sanitize_id(paper.paper_id)
        
        # Step 3: Execute boundary-aware text slicing
        text_slices = self._split_text_recursive(raw_text)
        document_chunks: List[DocumentChunk] = []

        # Step 4: Construct DocumentChunk records with SHA-256 content hashes
        for idx, slice_text in enumerate(text_slices):
            chunk_id = f"chunk_{clean_paper_id}_{idx:03d}"
            sha256 = self.compute_sha256(slice_text)
            
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                document_id=paper.paper_id,
                paper_title=paper.title,
                section_path="Abstract" if not paper.full_text else "Body",
                text=slice_text,
                chunk_index=idx,
                character_count=len(slice_text),
                sha256_hash=sha256,
            )
            document_chunks.append(chunk)

        return document_chunks

    def chunk_corpus(
        self,
        papers: List[Paper],
        output_path: Optional[str] = "data/corpus/chunks.json",
    ) -> List[DocumentChunk]:
        """
        Iterates over the entire paper corpus, generates chunks, and optionally persists to JSON.

        Args:
            papers: Collection of Paper models.
            output_path: Optional target file path for persisting generated chunks.

        Returns:
            Flat list of all generated DocumentChunk instances.
        """
        all_chunks: List[DocumentChunk] = []
        for paper in papers:
            chunks = self.chunk_paper(paper)
            all_chunks.extend(chunks)

        logger.info("Generated %d chunks from %d papers", len(all_chunks), len(papers))

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            serialized = [c.model_dump() for c in all_chunks]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
            logger.info("Saved %d chunks to %s", len(all_chunks), output_path)

        return all_chunks
