"""
FastAPI application factory and lifespan handler.

Startup sequence
----------------
1. EmbeddingService.initialize() — loads the sentence-transformers model
   (or validates Voyage AI key). This is the slow step (~2–5 s first run,
   instant on subsequent runs if the model is cached in ~/.cache).
2. Routers are mounted.

The app is intentionally stateless: all persistent state lives in
Postgres. Multiple workers (Gunicorn + Uvicorn) can run in parallel
without coordination.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

<<<<<<< HEAD
from LAYER2.layer2.app.routers import governance, ingest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from LAYER2.layer2.app.config import settings
from LAYER2.layer2.app.routers import search as search_router
from LAYER2.layer2.app.services.embedding import embedding_service
from LAYER2.layer2.app.services.neo4j_service import neo4j_service
from LAYER2.layer2.app.services.policy_engine import policy_engine
from LAYER2.layer2.app.services.sla_worker import sla_worker
=======
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ingest, search as search_router
from app.services.embedding import embedding_service
from app.services.neo4j_service import neo4j_service
>>>>>>> main

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan — runs once at startup and once at shutdown.
    Embedding model is loaded here so it's ready before the first request.
    Neo4j driver is initialised here; it no-ops if NEO4J_PASSWORD is unset.
    """
    logger.info("RFI Nexus Layer 2 starting up …")
    await embedding_service.initialize()
    logger.info("Embedding service ready.")
    await neo4j_service.initialize()
<<<<<<< HEAD
    await policy_engine.initialize()
    logger.info("Policy engine ready (OPA: %s).", settings.OPA_URL)
    sla_worker.start()
    yield
    await sla_worker.stop()
    await policy_engine.close()
=======
    yield
>>>>>>> main
    await neo4j_service.close()
    logger.info("RFI Nexus Layer 2 shutting down.")


app = FastAPI(
    title="RFI Nexus — Layer 2: Central Repository",
    description=(
        "Stores structured RFI records + vector embeddings. "
        "Provides semantic search (RFI-level and consideration-level), "
        "hybrid pgvector neo4j search, workflow state management, and a "
        "tamper-evident hash-chained audit trail.\n\n"
        "**Integration:** Layer 1 → POST /rfi | Layer 3+ → GET /rfi/{id}, "
        "POST /search, POST /search/hybrid"
    ),
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all origins in development; lock down in production via env vars.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
<<<<<<< HEAD
# Governance first: its /rfi/export and GET /rfi must be matched before
# ingest's /rfi/{rfi_uuid} parameterized route.
app.include_router(governance.router)
=======
>>>>>>> main
app.include_router(ingest.router)
app.include_router(search_router.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Meta"], summary="Health check")
async def health():
    return {
        "status": "ok",
        "embedding_backend": settings.EMBEDDING_BACKEND,
        "extraction_backend": settings.EXTRACTION_BACKEND,
        "auth_enabled": settings.AUTH_ENABLED,
        "env": settings.APP_ENV,
    }
