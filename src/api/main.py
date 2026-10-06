"""
FastAPI Main Application Entrypoint.

Architecture Role:
    Part of Phase 7 (FastAPI Application Service). Configures and initializes the production
    FastAPI application, registers CORS middleware, handles server lifespan events (graceful
    connection pool cleanup on shutdown), and mounts API route modules.

Inputs:
    - Application configuration from `Settings` via `get_settings()`.

Outputs:
    - Running ASGI application instance suitable for Uvicorn (`src.api.main:app`).

Design Decisions:
    - Async Lifespan Context: Manages startup diagnostics and guarantees database driver connection
      pools are gracefully closed on server shutdown.
    - CORS Policy: Permissive CORS configuration for development and frontend dashboard integration.
"""

from contextlib import asynccontextmanager
import os
from typing import Any, AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import get_coordinator, router as api_router
from src.core.config import get_settings
from src.core.logging import setup_logger

logger = setup_logger(name="api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages application startup diagnostics and graceful resource disposal on shutdown.
    """
    settings = get_settings()
    logger.info("Initializing Enterprise GraphRAG API (Debug: %s)", settings.debug)

    # Startup Warmup: Eagerly pre-warm coordinator singletons and DB pools
    try:
        coordinator = get_coordinator()
        if hasattr(coordinator, "warmup") and callable(coordinator.warmup):
            warmup_status = await coordinator.warmup()
            logger.info("Application startup warmup complete: %s", warmup_status)
    except Exception as exc:
        logger.warning("Application startup warmup encountered an error: %s", exc)

    # Yield control to the ASGI server runtime
    yield

    # Shutdown sequence: release database connection pools
    logger.info("Initiating graceful shutdown: disposing database connection pools...")
    coordinator = get_coordinator()

    try:
        await coordinator.query_engine.writer.close()
        logger.info("Neo4j driver connection closed.")
    except Exception as exc:
        logger.warning("Error closing Neo4j driver: %s", exc)

    try:
        await coordinator.vector_store.engine.dispose()
        logger.info("PostgreSQL engine connection pool disposed.")
    except Exception as exc:
        logger.warning("Error disposing PostgreSQL engine: %s", exc)


def create_application() -> FastAPI:
    """
    Factory function creating and configuring the primary FastAPI instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Enterprise Hybrid GraphRAG API",
        description=(
            "Hybrid Knowledge Graph and Dense Vector RAG system combining Neo4j "
            "property graph traversals with pgvector semantic similarity search, "
            "intent-driven query routing, and deterministic citation validation."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Step 1: Configure Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Step 2: Register API routers
    app.include_router(api_router, prefix="/api/v1")
    # Also include routes at root for standard /query and /health paths
    app.include_router(api_router)

    # Step 3: Mount Material 3 Static Web Application
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    # Step 4: Define Root Metadata Endpoint
    @app.get("/", tags=["System"])
    async def root_info(request: Request) -> Any:
        """Returns API identity or redirects interactive browsers to the Material 3 UI."""
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/ui/")
        return {
            "name": "Enterprise Hybrid GraphRAG API",
            "version": "0.1.0",
            "status": "online",
            "web_interface": "/ui/",
            "documentation": "/docs",
            "health_check": "/health",
            "acknowledgments": "Thank you to arXiv for use of its open access interoperability.",
        }

    return app


# Module-level ASGI application callable for Uvicorn
app = create_application()

