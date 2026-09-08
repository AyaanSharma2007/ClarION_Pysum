"""
neo4j_analytics.py — Neo4j graph operations for the analytics feature.

Creates and manages:
  - (:Department) nodes
  - (:Category) nodes (analytics category, NOT CTR_Articles)
  - (RFI)-[:SUBMITTED_BY]->(Department) relationships
  - (RFI)-[:HAS_CATEGORY]->(Category) relationships
  - (RFI)-[:IS_SIMILAR_TO {similarity: float}]->(RFI) relationships

These relationships power the analytics dashboard's department metrics,
repeating-topic detection, and redundancy rate calculations.

Usage:
    from apps.backend.app.neo4j_analytics import (
        merge_analytics_metadata,
        create_similarity_edge,
        get_repeating_topics,
        get_department_rfi_counts,
    )
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def _get_driver():
    """Lazy-load Neo4j driver. Returns None if credentials are missing."""
    if not NEO4J_URI or not NEO4J_PASSWORD:
        logger.debug("Neo4j credentials not configured — skipping.")
        return None
    try:
        from neo4j import GraphDatabase
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except ImportError:
        logger.warning("neo4j package not installed.")
        return None


def merge_analytics_metadata(
    rfi_id: str,
    department: str,
    category: str,
    urgency: str,
    summary: str,
) -> bool:
    """
    MERGE Department and Category nodes, and create relationships from an RFI.

    Creates:
      (RFI {rfi_id})-[:SUBMITTED_BY]->(Department {name})
      (RFI {rfi_id})-[:HAS_CATEGORY]->(Category {name})
      Sets rfi.urgency and rfi.summary properties.

    Returns True on success, False on failure.
    """
    driver = _get_driver()
    if not driver:
        return False

    MERGE_QUERY = """
    MERGE (rfi:RFI {rfi_id: $rfi_id})
    SET rfi.urgency = $urgency,
        rfi.summary = $summary

    MERGE (dept:Department {name: $department})
    MERGE (rfi)-[:SUBMITTED_BY]->(dept)

    MERGE (cat:Category {name: $category})
    MERGE (rfi)-[:HAS_CATEGORY]->(cat)
    """

    try:
        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    MERGE_QUERY,
                    rfi_id=rfi_id,
                    department=department,
                    category=category,
                    urgency=urgency,
                    summary=summary,
                )
            )
        driver.close()
        logger.info("Neo4j analytics metadata merged for %s", rfi_id)
        return True
    except Exception as e:
        logger.warning("Neo4j analytics merge failed for %s: %s", rfi_id, e)
        try:
            driver.close()
        except Exception:
            pass
        return False


def create_similarity_edge(
    source_rfi_id: str,
    target_rfi_id: str,
    similarity_score: float,
) -> bool:
    """
    Create an IS_SIMILAR_TO relationship between two RFI nodes.

    (RFI {rfi_id: source})-[:IS_SIMILAR_TO {similarity: score}]->(RFI {rfi_id: target})

    Uses MERGE to avoid duplicate edges.
    """
    driver = _get_driver()
    if not driver:
        return False

    SIMILARITY_QUERY = """
    MATCH (a:RFI {rfi_id: $source_rfi_id})
    MATCH (b:RFI {rfi_id: $target_rfi_id})
    MERGE (a)-[r:IS_SIMILAR_TO]->(b)
    SET r.similarity = $similarity_score
    """

    try:
        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    SIMILARITY_QUERY,
                    source_rfi_id=source_rfi_id,
                    target_rfi_id=target_rfi_id,
                    similarity_score=similarity_score,
                )
            )
        driver.close()
        logger.info(
            "Neo4j IS_SIMILAR_TO edge: %s -> %s (%.3f)",
            source_rfi_id, target_rfi_id, similarity_score,
        )
        return True
    except Exception as e:
        logger.warning("Neo4j similarity edge failed: %s", e)
        try:
            driver.close()
        except Exception:
            pass
        return False


def get_repeating_topics(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Query Neo4j for clusters of similar RFIs connected by IS_SIMILAR_TO edges.

    Returns grouped clusters with:
      - summary: representative summary text
      - department: originating department
      - frequency: number of RFIs in the cluster
      - rfi_ids: list of connected RFI IDs
    """
    driver = _get_driver()
    if not driver:
        return []

    CLUSTER_QUERY = """
    MATCH (a:RFI)-[r:IS_SIMILAR_TO]->(b:RFI)
    OPTIONAL MATCH (a)-[:SUBMITTED_BY]->(d:Department)
    WITH a, collect(DISTINCT b.rfi_id) AS similar_ids,
         a.summary AS summary,
         d.name AS department,
         avg(r.similarity) AS avg_similarity
    RETURN a.rfi_id AS rfi_id,
           summary,
           department,
           size(similar_ids) + 1 AS frequency,
           similar_ids,
           avg_similarity
    ORDER BY frequency DESC
    LIMIT $limit
    """

    try:
        with driver.session() as session:
            result = session.run(CLUSTER_QUERY, limit=limit)
            topics = []
            for record in result:
                topics.append({
                    "rfi_id": record["rfi_id"],
                    "summary": record["summary"] or "No summary available",
                    "department": record["department"] or "Unknown",
                    "frequency": record["frequency"],
                    "similar_rfi_ids": record["similar_ids"],
                    "avg_similarity": round(record["avg_similarity"] or 0, 3),
                })
        driver.close()
        return topics
    except Exception as e:
        logger.warning("Neo4j repeating topics query failed: %s", e)
        try:
            driver.close()
        except Exception:
            pass
        return []


def get_department_rfi_counts() -> List[Dict[str, Any]]:
    """
    Query Neo4j for the count of RFIs per department.
    """
    driver = _get_driver()
    if not driver:
        return []

    QUERY = """
    MATCH (rfi:RFI)-[:SUBMITTED_BY]->(d:Department)
    RETURN d.name AS department, count(rfi) AS count
    ORDER BY count DESC
    """

    try:
        with driver.session() as session:
            result = session.run(QUERY)
            return [{"department": r["department"], "count": r["count"]} for r in result]
    except Exception as e:
        logger.warning("Neo4j department counts query failed: %s", e)
        return []
    finally:
        try:
            driver.close()
        except Exception:
            pass
