from __future__ import annotations
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://rfi_user:rfi_pass@localhost:5432/rfi_nexus"
    )

    # Sync URL is needed by Alembic (psycopg3 driver instead of asyncpg)
    @property
    def SYNC_DATABASE_URL(self) -> str:
<<<<<<< HEAD
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        url = self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg://"
        )
        # Strip asyncpg-specific query params that psycopg doesn't understand
        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query)
            params.pop("prepared_statement_cache_size", None)
            new_query = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=new_query))
        return url
=======
        return self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg://"
        )
>>>>>>> main

    # ── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_BACKEND: Literal["sentence_transformers", "voyage", "dummy", "stub"] = (
        "sentence_transformers"
    )
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    VOYAGE_API_KEY: str | None = None

    # ── Entity Extraction ─────────────────────────────────────────────────────
    EXTRACTION_BACKEND: Literal["stub", "claude", "ollama", "local"] = "stub"
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"


    # ── Auth ──────────────────────────────────────────────────────────────────
    AUTH_ENABLED: bool = False
    SUPABASE_JWT_SECRET: str | None = None

    # ── Neo4j (Layer 3 graph — used for hybrid search enrichment) ─────────────
    # Leave NEO4J_PASSWORD unset to run in pgvector-only mode (safe for local dev).
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str | None = None
    NEO4J_DATABASE: str = "neo4j"

<<<<<<< HEAD
    # ── OPA Policy Engine (Bible §6.1) ────────────────────────────────────────
    # Fail-closed always. No environment-based toggle.
    # Rules being iterated on are excluded by ID via DISABLED_RULES (with
    # a startup warning printed every boot). All other rules stay enforced.
    OPA_URL: str = "http://localhost:8181"
    DISABLED_RULES: list[str] = []

=======
>>>>>>> main
    # ── Workflow ──────────────────────────────────────────────────────────────
    SLA_HOURS_DEFAULT: int = 72

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"


settings = Settings()
