"""
Document Metadata Resolver Module.

Architecture Role:
    Part of Phase 5 (Routing & Retrieval Coordination). Provides a dedicated, provenance-aware
    document catalog metadata resolution stage. Ingests canonical paper catalog metadata from
    `data/corpus/papers.json` and resolves author names, paper titles, venues, and publication
    identifiers without polluting dense text-chunk vector search.

Inputs:
    - User query string (raw or coreference-resolved).
    - Detected canonical entities from RouteClassifier or EntityResolver.

Outputs:
    - List of `MetadataEvidenceRecord` instances carrying explicit provenance:
      (id, paper_id, source='papers.json', field, title, authors, formatted_header).

Design Invariants:
    - Non-Indiscriminate Resolution: Only triggers when the query explicitly asks for or references
      document-level metadata (author names, paper titles, arXiv IDs, publication venues).
    - Separation of Concerns: Keeps metadata evidence distinct from vector text chunks to preserve
      clean `chunk_recall` and `metadata_recall` metric decoupling.
    - Zero Hallucination: Outputs catalog headers strictly verified against the authoritative
      document corpus (`papers.json`).
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import setup_logger

logger = setup_logger(name="router.metadata_resolver")

# Metadata intent detection pattern: author, publication, venue, title, citation queries
METADATA_INTENT_PATTERN = re.compile(
    r"\b(who (authored|wrote|are the (primary )?authors?)|authors?|researchers?|creators?|"
    r"written by|published (in|by|year)|publication year|venue|journal|conference|"
    r"arxiv id|doi|paper title|titled|study title)\b",
    re.IGNORECASE,
)

# Colleague / team citation pattern matching "Author et al." or "Author and colleagues"
AUTHOR_CITATION_PATTERN = re.compile(
    r"\b([A-Z][a-z]+)\s+(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))\b",
    re.IGNORECASE,
)

# Incidental author attribution pattern (non-metadata participial / relative clauses)
# e.g., "introduced by Zhishang Xiang et al.", "proposed by ...", "survey by ..."
INCIDENTAL_AUTHOR_PATTERN = re.compile(
    r"\b(?:introduced|proposed|developed|presented|created|designed|evaluated|identified|studied)\s+by\s+[A-Za-z\s]+?(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))|"
    r"\baccording\s+to\s+[A-Za-z\s]+?(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))|"
    r"\b(?:survey|paper|study|framework|benchmark)\s+by\s+[A-Za-z\s]+?(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))|"
    r"\b(?:design|evaluation|implementation)\s+of\s+[A-Za-z0-9\-_]+\s+by\s+[A-Za-z\s]+?(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))|"
    r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))",
    re.IGNORECASE,
)


class MetadataEvidenceRecord(BaseModel):
    """
    Structured, provenance-aware document catalog metadata evidence record.
    """
    id: str = Field(..., description="Canonical metadata identifier (e.g. meta_arxiv_2507_23581v2_authors)")
    paper_id: str = Field(..., description="Foreign key paper identifier (e.g. arxiv_2507.23581v2)")
    source: str = Field(default="papers.json", description="Authoritative origin of the metadata")
    field: str = Field(default="authors", description="Metadata field resolved (e.g. authors, title, venue)")
    title: str = Field(..., description="Official title of the paper")
    authors: List[str] = Field(default_factory=list, description="Full author names registered in catalog")
    published_year: Optional[int] = Field(default=None, description="Publication year")
    venue: Optional[str] = Field(default=None, description="Publication venue or journal")
    arxiv_id: Optional[str] = Field(default=None, description="Official ArXiv accession identifier")
    formatted_header: str = Field(..., description="Formatted markdown header block for prompt context injection")


class MetadataResolver:
    """
    Resolves document-level catalog metadata from `data/corpus/papers.json` for queries
    requesting or referencing author names, paper titles, venues, and publication IDs.
    """

    def __init__(self, catalog_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.catalog_path = Path(catalog_path or getattr(settings, "papers_catalog_path", "data/corpus/papers.json"))
        self._papers_by_id: Dict[str, Dict[str, Any]] = {}
        self._indexed_papers: List[Dict[str, Any]] = []
        self._load_catalog()

    def _load_catalog(self) -> None:
        """
        Loads and indexes the document corpus catalog from disk.
        """
        if not self.catalog_path.exists():
            logger.warning("Document catalog not found at %s; metadata resolver inactive", self.catalog_path)
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                papers = json.load(f)

            for p in papers:
                pid = p.get("paper_id", "")
                if not pid:
                    continue

                clean_pid = pid.replace(".", "_")
                canonical_id = f"meta_{clean_pid}_authors"
                title = p.get("title", "")
                authors = [a.get("name", "").strip() for a in p.get("authors", []) if a.get("name")]
                surnames = [
                    name.split()[-1].lower()
                    for name in authors
                    if len(name.split()[-1]) > 2
                ]
                acronym = title.split(":")[0].strip().lower()
                arxiv_id = (p.get("arxiv_id") or "").strip().lower()

                entry = {
                    "paper_id": pid,
                    "canonical_id": canonical_id,
                    "title": title,
                    "acronym": acronym,
                    "title_lower": title.lower(),
                    "authors": authors,
                    "authors_lower": [a.lower() for a in authors],
                    "surnames": surnames,
                    "published_year": p.get("published_year"),
                    "venue": p.get("venue"),
                    "arxiv_id": arxiv_id,
                }
                self._papers_by_id[pid] = entry
                self._indexed_papers.append(entry)

            logger.info("Loaded %d paper metadata records into MetadataResolver", len(self._indexed_papers))
        except Exception as exc:
            logger.error("Failed to load document catalog from %s: %s", self.catalog_path, exc)

    def resolve(
        self,
        query: str,
        detected_entities: Optional[List[str]] = None,
    ) -> List[MetadataEvidenceRecord]:
        """
        Resolves document metadata records for queries referencing or requesting document metadata.

        Triggers only when:
        1. Query has explicit metadata/authorship intent AND matches an author or paper title.
        2. Query has a standalone author citation reference (e.g. 'Kotoge et al.') where the
           paper title is not already named, and the author is not an incidental clause modifier.

        Does NOT trigger on incidental author mentions (e.g., 'introduced by Zhishang Xiang et al.').

        Returns:
            List of `MetadataEvidenceRecord` instances (empty if query does not target metadata).
        """
        if not self._indexed_papers:
            return []

        query_lower = query.lower()
        has_metadata_intent = bool(METADATA_INTENT_PATTERN.search(query_lower))
        detected_set = {e.lower() for e in (detected_entities or [])}

        # Filter out incidental author clauses from author searching when query lacks metadata intent
        clean_query = INCIDENTAL_AUTHOR_PATTERN.sub(" ", query_lower)
        target_author_query = query_lower if has_metadata_intent else clean_query

        matched_pids: Set[str] = set()

        for entry in self._indexed_papers:
            pid = entry["paper_id"]

            # Signal 1: Author mention
            author_hit = False
            for author_name in entry["authors_lower"]:
                if len(author_name) > 4 and author_name in target_author_query:
                    author_hit = True
                    break
                if author_name in detected_set and has_metadata_intent:
                    author_hit = True
                    break

            # Check surname citation pattern (e.g., "Kotoge et al." or "Kotoge and colleagues")
            if not author_hit:
                for surname in entry["surnames"]:
                    pat = rf"\b{re.escape(surname)}\s+(?:et\s+al\.?|and\s+(?:colleagues|coworkers|team))\b"
                    if re.search(pat, target_author_query):
                        author_hit = True
                        break

            # Signal 2: Paper title or acronym match
            title_hit = False
            acronym = entry["acronym"]
            if len(acronym) > 3 and (acronym in query_lower or acronym in detected_set):
                title_hit = True
            elif f"'{entry['title_lower']}'" in query_lower or f'"{entry["title_lower"]}"' in query_lower:
                title_hit = True
            elif entry["arxiv_id"] and entry["arxiv_id"] in query_lower:
                title_hit = True

            # Match Decision (ADR 052 / Run 3A):
            # 1. If query has metadata intent: trigger on paper title or author match
            # 2. If query lacks metadata intent: trigger ONLY on standalone author reference when title is not present
            if has_metadata_intent:
                if title_hit or author_hit:
                    matched_pids.add(pid)
            else:
                if author_hit and not title_hit:
                    matched_pids.add(pid)

        # Assemble provenance-aware records for matched papers
        records: List[MetadataEvidenceRecord] = []
        for pid in matched_pids:
            entry = self._papers_by_id[pid]
            authors_str = ", ".join(entry["authors"])
            header_lines = [
                "Document Catalog Header:",
                f"Paper Title: {entry['title']}",
                f"Authors: {authors_str}",
            ]
            if entry["arxiv_id"]:
                header_lines.append(f"ArXiv ID: {entry['arxiv_id']}")
            if entry["venue"]:
                venue_str = entry["venue"]
                if entry["published_year"]:
                    venue_str += f" ({entry['published_year']})"
                header_lines.append(f"Venue: {venue_str}")

            formatted_header = "\n".join(header_lines)

            records.append(
                MetadataEvidenceRecord(
                    id=entry["canonical_id"],
                    paper_id=pid,
                    source="papers.json",
                    field="authors",
                    title=entry["title"],
                    authors=entry["authors"],
                    published_year=entry["published_year"],
                    venue=entry["venue"],
                    arxiv_id=entry["arxiv_id"],
                    formatted_header=formatted_header,
                )
            )

        return records
