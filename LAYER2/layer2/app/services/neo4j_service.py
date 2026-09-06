"""
Neo4j enrichment service — Layer 3 graph query at search time.

This service is used exclusively by the ``POST /search/hybrid`` endpoint.
It takes a list of ``consideration_id_str`` values (the merge keys that
match ``Consideration.consideration_id`` in Neo4j) and returns graph-enriched
records: MSC country, Indication name, CTR article, Louvain cluster ID,
and centrality score.

Graceful degradation
--------------------
If ``NEO4J_PASSWORD`` is not set in ``.env``, ``initialize()`` is a no-op
and ``enrich_considerations()`` returns an empty list without raising.
This means ``POST /search/hybrid`` still works during local dev even before
Layer 3 is populated — it just returns pgvector hits with ``null`` graph fields
and ``neo4j_enriched: false`` in the response.

Switching databases
-------------------
Set ``NEO4J_DATABASE`` in ``.env`` to point at a named Neo4j database
(default: ``"neo4j"``).  All other Neo4j connection params are also in ``.env``.
"""
from __future__ import annotations

import logging
from typing import Any

from LAYER2.layer2.app.config import settings

logger = logging.getLogger(__name__)


class Neo4jService:
    def __init__(self) -> None:
        self._driver: Any = None
        self._available = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Called once at FastAPI startup (lifespan).
        No-ops safely if NEO4J_PASSWORD is not configured — this lets
        the app start in local dev without a running Neo4j instance.
        """
        if not settings.NEO4J_PASSWORD:
            logger.info(
                "Neo4j: NEO4J_PASSWORD not set — hybrid search will run "
                "in pgvector-only mode (graph fields will be null)."
            )
            return

        try:
            from neo4j import AsyncGraphDatabase  # type: ignore[import]

            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            # Verify connectivity at startup rather than at first request.
            await self._driver.verify_connectivity()
            self._available = True
            logger.info(
                "Neo4j connected: %s  database=%s",
                settings.NEO4J_URI,
                settings.NEO4J_DATABASE,
            )
        except ImportError:
            logger.warning(
                "neo4j package not installed — install with: pip install neo4j>=5.0  "
                "Hybrid search will run in pgvector-only mode."
            )
        except Exception as exc:
            logger.warning(
                "Neo4j connection failed (%s) — hybrid search will run in "
                "pgvector-only mode.  Check NEO4J_URI / credentials in .env.",
                exc,
            )

    async def close(self) -> None:
        """Called at FastAPI shutdown."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            self._available = False

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True when a live Neo4j connection exists."""
        return self._available

    async def enrich_considerations(
        self, consideration_ids: list[str]
    ) -> list[dict]:
        """
        Fetch graph context for a batch of consideration_id_str values.

        Parameters
        ----------
        consideration_ids:
            List of Neo4j merge keys, e.g. ``["CT-2024-123-C1", "CT-2024-123-C2"]``.
            These must match ``Consideration.consideration_id`` in Neo4j exactly.

        Returns
        -------
        List of dicts with keys:
            consideration_id, concern_text, rfi_id,
            msc_country, indication_name, ctr_article_name,
            louvain_cluster, centrality

        Returns ``[]`` if Neo4j is unavailable or the list is empty.
        """
        if not self._available or not consideration_ids:
            return []

        async with self._driver.session(
            database=settings.NEO4J_DATABASE
        ) as session:
            result = await session.run(
                """
                MATCH (c:Consideration)<-[:HAS_CONSIDERATION]-(r:RFI)
                      -[:SUBMITTED_TO]->(m:MSC)
                MATCH (r)-[:INDICATION_TO]->(i:Indication)
                OPTIONAL MATCH (c)-[:REFERENCES]->(art:CTR_Articles)
                WHERE c.consideration_id IN $ids
                RETURN
                    c.consideration_id   AS consideration_id,
                    c.concern_text       AS concern_text,
                    r.rfi_id             AS rfi_id,
                    m.msc_country        AS msc_country,
                    i.indication_name    AS indication_name,
                    art.ctr_article_name AS ctr_article_name,
                    c.louvain_cluster    AS louvain_cluster,
                    c.centrality         AS centrality
                """,
                ids=consideration_ids,
            )
            return [dict(record) for record in await result.data()]


# Module-level singleton — shared across all request contexts.
neo4j_service = Neo4jService()
