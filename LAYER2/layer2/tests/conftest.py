"""
Test fixtures and shared test utilities.

Tests use an async HTTPX client backed by the FastAPI app, connected to the
same docker-compose Postgres stack used for development.

Requirements before running:
    docker compose up -d
    alembic upgrade head
    pytest tests/ -v          ← run from the layer2/ directory

To override the DB URL in CI:
    export TEST_DATABASE_URL=postgresql+asyncpg://...
    pytest tests/ -v
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from LAYER2.layer2.app.main import app
from LAYER2.layer2.app.database import Base, get_db
from LAYER2.layer2.app.config import settings
from LAYER2.layer2.app.services.embedding import embedding_service

# ── DB URL ─────────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", settings.DATABASE_URL)


# ── DB setup/teardown (session-scoped) ─────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """
    Create all tables before tests run; drop them after.
    The engine is created HERE (inside the session event loop) so asyncpg
    never gets a 'Future attached to a different loop' error.
    """
    import sqlalchemy as sa

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create schema
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Initialize embedding service so search tests don't get 503
    await embedding_service.initialize()

    # Override the get_db dependency to use the test engine
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    yield

    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── HTTP client ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    """Async HTTP client bound to the FastAPI app (no live server needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Shared sample payload ──────────────────────────────────────────────────────

SAMPLE_RFI = {
    "rfi_id": "CT-2024-123456-12-00-SM01-001",
    "due_date": "2026-03-16",
    "response_date": "2026-03-06",
    "submit_date": "2026-03-05",
    "msc": {"country": "Germany"},
    "indication": {"name": "Type 2 Diabetes Mellitus"},
    "considerations": [
        {
            "number": 1,
            "concern_text": (
                "Please provide proof of payment of the additional fee "
                "required for this validation procedure."
            ),
            "ctr_article": {"name": "Part I - Regulatory / Annex I, Section 63"},
            "response": {"text": "Proof of payment of the additional amount required is provided."},
            "outcome": None,
        }
    ],
    "owner_team": "CTA Management",
}
