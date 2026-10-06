"""
Corpus Ingestion & Paper Collector Module.

Architecture Role:
    Part of Phase 1 (Ingestion). Gathers academic and technical papers from public APIs
    (arXiv and Semantic Scholar) to populate the raw corpus directory (`data/corpus/`).
    The collected papers serve as the raw input for both the Knowledge Graph extractor
    and the Dense Vector indexer.

Inputs:
    - Search query topic (e.g., 'retrieval-augmented generation')
    - Maximum paper count limit
    - API keys from environment settings (`ARXIV_USER_AGENT`, `SEMANTIC_SCHOLAR_API_KEY`)

Outputs:
    - List of structured `Paper` domain models (with title, abstract, authors, year, citation links)
    - Serialized JSON corpus file (e.g., `data/corpus/papers.json`)

Design Decisions & Constraints:
    - Polite Rate Limiting: arXiv enforces a strict >= 3.0 second delay between requests.
    - Windows TLS Workaround: Python SSL on Windows sometimes triggers HTTP 406 on arXiv
      during TLS session renegotiation; handled via an automatic `curl.exe` transport fallback.
    - Structured Citations: Semantic Scholar API provides direct reference/citation graph links.
"""

import asyncio
import json
import os
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import httpx

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.ingestion.models import Author, Paper

logger = setup_logger(name="ingestion.collector")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
DEFAULT_CORPUS_SIZE = 50       # Default number of papers to harvest if unspecified
MAX_BATCH_SIZE = 100           # Maximum batch size supported per single API request
MAX_RETRIES = 3                # Maximum retry attempts on transient network errors
INITIAL_BACKOFF_SECONDS = 3.0  # Base delay for exponential backoff on HTTP 429/503
HTTP_TIMEOUT_SECONDS = 30.0    # Network timeout per HTTP request

# API Endpoints & XML Namespaces
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_BASE_URL = "https://export.arxiv.org/api/query"
ARXIV_XML_NAMESPACE = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class PaperCollector:
    """
    Orchestrates robust, rate-limited harvesting of scientific literature from public APIs.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.last_arxiv_call_time: float = 0.0

    async def _polite_arxiv_throttle(self) -> None:
        """
        Enforces the mandatory arXiv API policy of >= 3.0 seconds between consecutive calls.
        Calculates time elapsed since the last request and sleeps for the remainder if necessary.
        """
        elapsed = time.time() - self.last_arxiv_call_time
        required_delay = self.settings.arxiv_delay_seconds
        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            logger.debug("Throttling arXiv request for %.2f seconds to comply with API policy", wait_time)
            await asyncio.sleep(wait_time)
        self.last_arxiv_call_time = time.time()

    async def fetch_from_semantic_scholar(
        self,
        query: str,
        limit: int = DEFAULT_CORPUS_SIZE,
    ) -> List[Paper]:
        """
        Fetches papers with structured citation edges from Semantic Scholar API.

        Args:
            query: Topic or keyword search (e.g. 'retrieval-augmented generation')
            limit: Maximum number of papers to retrieve

        Returns:
            List of validated Paper model instances.
        """
        # ----------------------------------------------------------------------
        # Step 1: Prepare Request Headers & Parameters
        # ----------------------------------------------------------------------
        papers: List[Paper] = []
        headers: Dict[str, str] = {
            "User-Agent": self.settings.arxiv_user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
        }
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key

        params = {
            "query": query,
            "limit": min(limit, MAX_BATCH_SIZE),
            "fields": "paperId,title,abstract,authors,year,venue,citationCount,references,citations,externalIds",
        }

        logger.info("Querying Semantic Scholar API for: '%s' (limit=%d)", query, limit)

        # ----------------------------------------------------------------------
        # Step 2: Execute Async HTTP Request with Exponential Backoff
        # ----------------------------------------------------------------------
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.get(
                        SEMANTIC_SEARCH_URL if "SEMANTIC_SEARCH_URL" in globals() else SEMANTIC_SCHOLAR_SEARCH_URL,
                        params=params,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("data", [])
                        
                        # Step 3: Parse and Structure Paper Domain Models
                        for item in items:
                            authors = [
                                Author(
                                    name=a.get("name", "Unknown"),
                                    affiliation=None,
                                )
                                for a in item.get("authors", [])
                                if a.get("name")
                            ]
                            external_ids = item.get("externalIds") or {}
                            arxiv_id = external_ids.get("ArXiv")
                            doi = external_ids.get("DOI")

                            # Extract citation graph relationships (references and citing papers)
                            references = [
                                ref.get("paperId")
                                for ref in item.get("references", [])
                                if ref.get("paperId")
                            ]
                            citations = [
                                cite.get("paperId")
                                for cite in item.get("citations", [])
                                if cite.get("paperId")
                            ]

                            paper = Paper(
                                paper_id=item.get("paperId", f"s2_{len(papers)}"),
                                title=item.get("title", "").strip(),
                                abstract=item.get("abstract", "") or "",
                                authors=authors,
                                published_year=item.get("year"),
                                venue=item.get("venue"),
                                arxiv_id=arxiv_id,
                                doi=doi,
                                citation_count=item.get("citationCount", 0),
                                references=references,
                                citations=citations,
                            )
                            papers.append(paper)
                        logger.info("Successfully fetched %d papers from Semantic Scholar", len(papers))
                        return papers

                    elif response.status_code in (429, 503):
                        # Exponential backoff on rate-limiting or server load
                        backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(
                            "Semantic Scholar rate-limited (HTTP %d). Backing off for %.1fs (attempt %d/%d)",
                            response.status_code,
                            backoff,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error("Semantic Scholar API returned HTTP %d: %s", response.status_code, response.text)
                        break

                except httpx.RequestError as exc:
                    logger.warning("Request error on Semantic Scholar call: %s. Retrying...", exc)
                    await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (attempt + 1))

        logger.warning("Semantic Scholar retrieval failed or returned 0 items. Falling back to arXiv.")
        return papers

    async def fetch_from_arxiv(
        self,
        query: str,
        limit: int = DEFAULT_CORPUS_SIZE,
    ) -> List[Paper]:
        """
        Fetches papers directly from arXiv API following strict polite policies.

        Args:
            query: Search query for arXiv (e.g. 'all:retrieval-augmented generation')
            limit: Total papers to fetch

        Returns:
            List of parsed Paper instances.
        """
        # ----------------------------------------------------------------------
        # Step 1: Format Query & Request Headers
        # ----------------------------------------------------------------------
        papers: List[Paper] = []
        formatted_query = f"all:{query}" if not query.startswith("all:") else query
        params = {
            "search_query": formatted_query,
            "start": 0,
            "max_results": min(limit, MAX_BATCH_SIZE),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        headers = {
            "User-Agent": self.settings.arxiv_user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
        }

        logger.info("Querying arXiv API for: '%s' (limit=%d)", formatted_query, limit)

        # ----------------------------------------------------------------------
        # Step 2: Rate-Limited Async Query with Retry and Windows Fallback
        # ----------------------------------------------------------------------
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            for attempt in range(MAX_RETRIES):
                # Polite throttle enforces mandatory delay between requests
                await self._polite_arxiv_throttle()
                try:
                    response = await client.get(
                        ARXIV_API_BASE_URL,
                        params=params,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        # Step 3: Parse Atom XML Response
                        root = ET.fromstring(response.text)
                        entries = root.findall("atom:entry", ARXIV_XML_NAMESPACE)

                        for entry in entries:
                            id_elem = entry.find("atom:id", ARXIV_XML_NAMESPACE)
                            title_elem = entry.find("atom:title", ARXIV_XML_NAMESPACE)
                            summary_elem = entry.find("atom:summary", ARXIV_XML_NAMESPACE)
                            published_elem = entry.find("atom:published", ARXIV_XML_NAMESPACE)

                            raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                            arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id
                            title = " ".join(title_elem.text.split()) if title_elem is not None and title_elem.text else ""
                            abstract = " ".join(summary_elem.text.split()) if summary_elem is not None and summary_elem.text else ""

                            # Parse author list
                            authors: List[Author] = []
                            for author_elem in entry.findall("atom:author", ARXIV_XML_NAMESPACE):
                                name_elem = author_elem.find("atom:name", ARXIV_XML_NAMESPACE)
                                if name_elem is not None and name_elem.text:
                                    authors.append(Author(name=name_elem.text.strip()))

                            year: Optional[int] = None
                            if published_elem is not None and published_elem.text:
                                try:
                                    year = int(published_elem.text[:4])
                                except ValueError:
                                    year = None

                            paper = Paper(
                                paper_id=f"arxiv_{arxiv_id}",
                                title=title,
                                abstract=abstract,
                                authors=authors,
                                published_year=year,
                                venue="arXiv",
                                arxiv_id=arxiv_id,
                                citation_count=0,
                            )
                            papers.append(paper)

                        logger.info("Successfully fetched %d papers from arXiv API", len(papers))
                        return papers

                    elif response.status_code == 406:
                        # On Windows, arXiv TLS renegotiation sometimes triggers 406 on Python SSL.
                        # Fallback to system curl with schannel for 100% reliable retrieval.
                        logger.warning("arXiv returned HTTP 406 on httpx. Utilizing system curl transport fallback...")
                        import subprocess
                        import urllib.parse
                        encoded_query = urllib.parse.quote_plus(formatted_query)
                        full_url = f"{ARXIV_API_BASE_URL}?search_query={encoded_query}&start=0&max_results={min(limit, MAX_BATCH_SIZE)}&sortBy=relevance&sortOrder=descending"
                        
                        proc = await asyncio.to_thread(
                            subprocess.run,
                            ["curl.exe", "-s", "-A", self.settings.arxiv_user_agent, full_url],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                        )
                        if proc.returncode == 0 and proc.stdout.strip().startswith("<?xml"):
                            root = ET.fromstring(proc.stdout)
                            entries = root.findall("atom:entry", ARXIV_XML_NAMESPACE)
                            for entry in entries:
                                id_elem = entry.find("atom:id", ARXIV_XML_NAMESPACE)
                                title_elem = entry.find("atom:title", ARXIV_XML_NAMESPACE)
                                summary_elem = entry.find("atom:summary", ARXIV_XML_NAMESPACE)
                                published_elem = entry.find("atom:published", ARXIV_XML_NAMESPACE)

                                raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                                arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id
                                title = " ".join(title_elem.text.split()) if title_elem is not None and title_elem.text else ""
                                abstract = " ".join(summary_elem.text.split()) if summary_elem is not None and summary_elem.text else ""

                                authors: List[Author] = []
                                for author_elem in entry.findall("atom:author", ARXIV_XML_NAMESPACE):
                                    name_elem = author_elem.find("atom:name", ARXIV_XML_NAMESPACE)
                                    if name_elem is not None and name_elem.text:
                                        authors.append(Author(name=name_elem.text.strip()))
                            

                                year = None
                                if published_elem is not None and published_elem.text:
                                    try:
                                        year = int(published_elem.text[:4])
                                    except ValueError:
                                        year = None

                                papers.append(
                                    Paper(
                                        paper_id=f"arxiv_{arxiv_id}",
                                        title=title,
                                        abstract=abstract,
                                        authors=authors,
                                        published_year=year,
                                        venue="arXiv",
                                        arxiv_id=arxiv_id,
                                        citation_count=0,
                                    )
                                )
                            logger.info("Successfully fetched %d papers from arXiv via system transport fallback", len(papers))
                            return papers
                        break

                    elif response.status_code in (429, 503):
                        backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)
                        logger.warning("arXiv rate limit (HTTP %d). Backing off %.1fs", response.status_code, backoff)
                        await asyncio.sleep(backoff)
                    else:
                        logger.error("arXiv API returned HTTP %d", response.status_code)
                        break

                except Exception as exc:
                    logger.error("Error fetching from arXiv: %s", exc)
                    await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (attempt + 1))

        return papers

    async def collect_corpus(
        self,
        query: str = "retrieval-augmented generation",
        limit: int = DEFAULT_CORPUS_SIZE,
        output_path: str = "data/corpus/papers.json",
    ) -> List[Paper]:
        """
        Orchestrates paper collection:
        - Uses arXiv API directly by default (reliable, open public access with polite 3s rate limits).
        - If SEMANTIC_SCHOLAR_API_KEY is configured, queries Semantic Scholar for structured citation edges.
        """
        papers: List[Paper] = []
        
        # Step 1: If Semantic Scholar key is present, attempt citation-enriched retrieval
        if self.settings.semantic_scholar_api_key:
            logger.info("Semantic Scholar API key detected. Querying Semantic Scholar for citation graphs...")
            papers = await self.fetch_from_semantic_scholar(query=query, limit=limit)

        # Step 2: Fall back to primary arXiv API collector if needed
        if not papers:
            logger.info("Gathering papers from primary arXiv API collector...")
            papers = await self.fetch_from_arxiv(query=query, limit=limit)

        # Step 3: Ensure parent output directory exists and persist JSON corpus
        if papers:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            serialized = [p.model_dump() for p in papers]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
            logger.info("Saved %d papers to %s", len(papers), output_path)

        return papers


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect academic papers for GraphRAG corpus.")
    parser.add_argument("--query", type=str, default="retrieval-augmented generation", help="Search query")
    parser.add_argument("--limit", type=int, default=50, help="Number of papers to collect")
    parser.add_argument("--output", type=str, default="data/corpus/papers.json", help="Output JSON path")
    args = parser.parse_args()

    collector = PaperCollector()
    asyncio.run(collector.collect_corpus(query=args.query, limit=args.limit, output_path=args.output))

