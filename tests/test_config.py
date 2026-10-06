"""
Unit Tests for Core Configuration and Structured Logging.

Architecture Role:
    Validates Phase 0 (Foundation & Infrastructure). Ensures that environment settings,
    API keys, database connection strings, and centralized logging handlers initialize
    correctly and adhere to system-wide invariants before any services start.

Invariants Tested:
    1. Settings loads default ports (8000), valid PostgreSQL async URIs, Bolt URIs, and >= 3.0s arXiv delay.
    2. Setup logger returns a configured logger instance with correct name and log level hierarchy.
"""

from src.core.config import Settings, get_settings
from src.core.logging import setup_logger


def test_settings_initialization() -> None:
    """
    Test Objective:
        Verify that `Settings` singleton initializes properly with valid default attributes
        and environment overrides.

    Assertions:
        - Returned object is an instance of `Settings`.
        - Default FastAPI port is 8000.
        - PostgreSQL URI specifies the asyncpg async driver.
        - Neo4j URI uses the Bolt protocol.
        - arXiv throttle delay meets or exceeds the mandatory 3.0s policy.
    """
    # Step 1: Retrieve cached settings singleton
    settings = get_settings()

    # Step 2: Validate settings type and default port
    assert isinstance(settings, Settings)
    assert settings.app_port == 8000

    # Step 3: Validate database connection URIs
    assert "postgresql+asyncpg://" in settings.postgres_async_uri
    assert settings.neo4j_uri.startswith("bolt://")

    # Step 4: Validate arXiv API compliance parameters
    assert settings.arxiv_delay_seconds >= 3.0
    assert settings.arxiv_acknowledgment == "Thank you to arXiv for use of its open access interoperability."


def test_logger_setup() -> None:
    """
    Test Objective:
        Verify that `setup_logger` creates a named logger with proper handlers and level hierarchy.

    Assertions:
        - Logger name matches requested component identifier.
        - Logger level correctly resolves string 'DEBUG' to integer constant 10.
    """
    # Step 1: Initialize logger with custom name and explicit DEBUG level
    logger = setup_logger(name="test_logger", level="DEBUG")

    # Step 2: Verify logger name and level properties
    assert logger.name == "test_logger"
    assert logger.level == 10  # logging.DEBUG constant equals 10
