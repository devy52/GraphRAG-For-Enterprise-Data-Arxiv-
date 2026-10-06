"""Ingestion package for paper gathering, parsing, and chunking."""
from .models import Author, Paper, DocumentChunk, IngestRequest, IngestStatusResponse
from .collector import PaperCollector
from .chunker import DocumentChunker

__all__ = [
    "Author",
    "Paper",
    "DocumentChunk",
    "IngestRequest",
    "IngestStatusResponse",
    "PaperCollector",
    "DocumentChunker",
]
