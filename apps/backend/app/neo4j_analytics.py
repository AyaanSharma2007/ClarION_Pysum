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
    uri = os.getenv("NEO4J_URI") or NEO4J_URI
    user = os.getenv("NEO4J_USER") or NEO4J_USER or "neo4j"
    pwd = os.getenv("NEO4J_PASSWORD") or NEO4J_PASSWORD

    if not uri or not pwd:
        # Attempt to load from apps/backend/.env if not yet loaded in environment
        try:
            from dotenv import load_dotenv
            backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
            if os.path.exists(backend_env):
                load_dotenv(backend_env)
                uri = os.getenv("NEO4J_URI")
                user = os.getenv("NEO4J_USER", "neo4j")
                pwd = os.getenv("NEO4J_PASSWORD")
        except Exception:
            pass

    if not uri or not pwd:
        logger.debug("Neo4j credentials not configured — skipping.")
        return None
    try:
        from neo4j import GraphDatabase
        return GraphDatabase.driver(uri, auth=(user, pwd))
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

    Returns grouped disjoint topic clusters where:
      - summary: representative summary text for the cluster
      - department: originating department
      - frequency: total count of unique RFIs in the repeating cluster
      - similar_rfi_ids: list of connected RFI IDs
      - avg_similarity: true mean cosine similarity from graph edges
    """
    driver = _get_driver()
    if not driver:
        return []

    EDGE_QUERY = """
    MATCH (a:RFI)-[r:IS_SIMILAR_TO]->(b:RFI)
    OPTIONAL MATCH (a)-[:SUBMITTED_BY]->(da:Department)
    OPTIONAL MATCH (b)-[:SUBMITTED_BY]->(db:Department)
    RETURN a.rfi_id AS a_id, a.summary AS a_summary, da.name AS a_dept,
           b.rfi_id AS b_id, b.summary AS b_summary, db.name AS b_dept,
           r.similarity AS similarity
    """

    try:
        with driver.session() as session:
            records = list(session.run(EDGE_QUERY))
        driver.close()

        if not records:
            return []

        from collections import defaultdict

        adj = defaultdict(set)
        node_info = {}
        edge_sims = defaultdict(list)

        for rec in records:
            a_id, b_id = rec["a_id"], rec["b_id"]
            if not a_id or not b_id or a_id == b_id:
                continue
            sim = float(rec["similarity"] or 0)
            adj[a_id].add(b_id)
            adj[b_id].add(a_id)

            pair = tuple(sorted([a_id, b_id]))
            edge_sims[pair].append(sim)

            if a_id not in node_info:
                node_info[a_id] = {
                    "summary": rec["a_summary"] or "No summary available",
                    "dept": rec["a_dept"] or "Regulatory Affairs"
                }
            if b_id not in node_info:
                node_info[b_id] = {
                    "summary": rec["b_summary"] or "No summary available",
                    "dept": rec["b_dept"] or "Regulatory Affairs"
                }

        # Find connected components (disjoint clusters) via BFS
        visited = set()
        clusters = []

        for node in adj:
            if node in visited:
                continue
            comp = set()
            queue = [node]
            visited.add(node)
            while queue:
                curr = queue.pop(0)
                comp.add(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            comp_list = sorted(list(comp))
            sims = []
            for i in range(len(comp_list)):
                for j in range(i + 1, len(comp_list)):
                    pair = (comp_list[i], comp_list[j])
                    if pair in edge_sims:
                        sims.extend(edge_sims[pair])

            avg_sim = round(float(sum(sims) / len(sims)), 4) if sims else 1.0

            # Pick the most representative summary for this cluster:
            # Prefer node with highest degree in the cluster; tie-break by length of summary
            rep_node = max(comp_list, key=lambda n: (len(adj[n]), len(node_info[n]["summary"] or "")))
            summary = node_info[rep_node]["summary"]
            dept = node_info[rep_node]["dept"]

            clusters.append({
                "summary": summary,
                "department": dept,
                "frequency": len(comp),
                "similar_rfi_ids": comp_list,
                "avg_similarity": avg_sim,
            })

        # Sort clusters descending by frequency, then avg_similarity
        clusters.sort(key=lambda x: (x["frequency"], x["avg_similarity"]), reverse=True)
        return clusters[:limit]

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
