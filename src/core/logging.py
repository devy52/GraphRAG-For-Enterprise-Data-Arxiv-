"""
Centralized Logging Configuration Module.

Architecture Role:
    Part of Phase 0 (Foundation & Infrastructure). Provides structured, uniform console
    logging across all ingestion, graph extraction, vector indexing, query routing, and API modules.

Inputs:
    - Module name (e.g. 'ingestion.collector', 'graph.extractor', 'vector.indexer').
    - Optional log level override ('DEBUG', 'INFO', 'WARNING', 'ERROR').

Outputs:
    - Standard library `logging.Logger` instance formatted with timestamps and log levels.

Design Decisions:
    - Handler Idempotency: Checks `if not logger.handlers` before attaching a `StreamHandler`
      to prevent duplicate log output when loggers are re-instantiated in multiple modules.
    - Timestamp Precision: Formats log output as `YYYY-MM-DD HH:MM:SS [LEVEL] [NAME] MESSAGE`.
"""

import logging
import sys
from typing import Optional

def setup_logger(
    name: str = "graphrag",
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Configures and returns a named logger instance.
    
    Args:
        name: The hierarchical name of the component (e.g. 'graph.resolver').
        level: Optional log level string override (e.g. 'DEBUG', 'INFO').
        
    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    
    # Step 1: Prevent duplicate handlers if the logger has already been configured
    if not logger.handlers:
        if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
            import io
            stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
            handler = logging.StreamHandler(stream)
        else:
            handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    # Step 2: Set the runtime log level (defaults to INFO)
    log_level_str = level or "INFO"
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    return logger