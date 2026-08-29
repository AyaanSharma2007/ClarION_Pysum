"""
Embedding service — wraps sentence-transformers (local default) or Voyage AI.

Usage
-----
The module-level singleton `embedding_service` is initialized once at app
startup via the FastAPI lifespan. All routers access it through that singleton:

    from app.services.embedding import embedding_service
    vec = await embedding_service.encode_async(text)

Switching backends
------------------
Set EMBEDDING_BACKEND=voyage and VOYAGE_API_KEY=<key> in .env.
The vector dimension changes (384 → 1536), so you must also:
  1. Update EMBEDDING_DIMENSION=1536 in .env.
  2. Run a new Alembic migration to ALTER the vector column dimension.
  3. Re-embed all existing records (run the backfill script in scripts/).
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._backend = settings.EMBEDDING_BACKEND
        self._model: Any = None
        self._voyage_client: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Called once at app startup (FastAPI lifespan)."""
        if self._backend == "sentence_transformers":
            # Import deferred so the module loads fast even if torch is slow.
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading sentence-transformers model: %s", settings.EMBEDDING_MODEL
            )
            # SentenceTransformer() is synchronous — acceptable at startup.
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model ready (dim=%d).", settings.EMBEDDING_DIMENSION)

        elif self._backend == "voyage":
            if not settings.VOYAGE_API_KEY:
                raise ValueError(
                    "EMBEDDING_BACKEND=voyage requires VOYAGE_API_KEY to be set in .env"
                )
            import voyageai  # type: ignore[import]

            self._voyage_client = voyageai.AsyncClient(
                api_key=settings.VOYAGE_API_KEY
            )
            logger.info(
                "Voyage AI client initialized (model=%s).", settings.EMBEDDING_MODEL
            )

        self._initialized = True

    # ── Public API ─────────────────────────────────────────────────────────────

    def encode(self, text: str) -> list[float]:
        """
        Synchronous encode — only supported for sentence_transformers.
        Used in tests and scripts where async context is unavailable.
        """
        self._assert_ready()
        if self._backend == "sentence_transformers":
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        raise RuntimeError(
            "encode() is synchronous and not supported for the 'voyage' backend. "
            "Use encode_async() instead."
        )

    async def encode_async(self, text: str) -> list[float]:
        """
        Async encode — works for both backends.
        Preferred method for use inside FastAPI route handlers.
        """
        self._assert_ready()
        if self._backend == "sentence_transformers":
            # sentence-transformers is CPU/GPU sync; run in executor if needed.
            # For models this size it's fast enough inline.
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()

        elif self._backend == "voyage":
            result = await self._voyage_client.embed(
                [text],
                model=settings.EMBEDDING_MODEL,
                input_type="document",
            )
            return result.embeddings[0]

        raise RuntimeError(f"Unknown embedding backend: {self._backend}")

    async def encode_batch_async(self, texts: list[str]) -> list[list[float]]:
        """Batch encode — more efficient than calling encode_async in a loop."""
        self._assert_ready()
        if self._backend == "sentence_transformers":
            vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
            return [v.tolist() for v in vecs]

        elif self._backend == "voyage":
            result = await self._voyage_client.embed(
                texts,
                model=settings.EMBEDDING_MODEL,
                input_type="document",
            )
            return result.embeddings

        raise RuntimeError(f"Unknown embedding backend: {self._backend}")

    # ── Private ────────────────────────────────────────────────────────────────

    def _assert_ready(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "EmbeddingService has not been initialized. "
                "This usually means app startup (lifespan) did not complete."
            )


# Module-level singleton — shared across all request contexts.
embedding_service = EmbeddingService()
