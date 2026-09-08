"""
analytics_enrichment.py — RFI analytics enrichment pipeline.

This module is called during RFI ingestion to:
  1. Prompt Qwen-1.5B for strict JSON extraction (department, category, urgency, summary)
  2. Generate a 384-dim embedding from the summary using sentence-transformers/all-MiniLM-L6-v2
  3. Run pgvector similarity search to detect duplicate/redundant RFIs (threshold > 0.85)
  4. Store enriched metadata + embedding in Supabase
  5. Create Neo4j analytics relationships (Department, Category, IS_SIMILAR_TO)

Usage:
    from apps.backend.app.analytics_enrichment import enrich_rfi_analytics
    result = await enrich_rfi_analytics(rfi_id, concern_texts, supabase_client)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# ── Lazy-loaded sentence-transformers model ──────────────────────────────────
_embedding_model = None


def _get_embedding_model():
    """Lazy-load the sentence-transformers model on first use."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers/all-MiniLM-L6-v2 embedding model.")
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            raise
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """
    Generate a 384-dimensional embedding vector from text using all-MiniLM-L6-v2.

    Args:
        text: The input text to embed (typically the Qwen-generated summary).

    Returns:
        A list of 384 floats representing the embedding vector.
    """
    model = _get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


# ── Qwen JSON Extraction ─────────────────────────────────────────────────────

ANALYTICS_EXTRACTION_PROMPT = """You are an expert regulatory document analyst. Analyze the following RFI (Request for Information) text and extract structured metadata.

You MUST respond with ONLY a valid JSON object. No explanations, no markdown, no extra text.

The JSON MUST have exactly these four fields:
{
  "department": "the department or functional area this RFI relates to (e.g., 'Regulatory Affairs', 'Clinical Operations', 'Quality Assurance', 'Pharmacovigilance', 'Medical Writing', 'Statistics', 'CMC', 'Legal')",
  "category": "the topic category of the concern (e.g., 'Protocol Design', 'Safety Reporting', 'Data Integrity', 'Informed Consent', 'GMP Compliance', 'Labeling', 'Bioequivalence', 'Documentation')",
  "urgency": "High or Medium or Low",
  "summary": "A single clear sentence summarizing the core problem or question raised."
}

Rules:
- "department" must be a real department name, NOT a country or person name.
- "category" must describe the TOPIC of the concern, not the document type.
- "urgency": High = patient safety or major deficiency; Medium = significant but not safety-critical; Low = minor administrative or clarification.
- "summary" must be exactly ONE sentence, max 50 words, describing the problem.

RFI TEXT:
"""


async def extract_analytics_json(concern_texts: List[str]) -> Dict[str, str]:
    """
    Prompt Qwen-1.5B via Ollama to extract analytics metadata from RFI text.

    Sends concatenated concern texts to the model with a strict JSON extraction
    prompt. Parses the response and validates required fields.

    Args:
        concern_texts: List of concern text strings from the RFI considerations.

    Returns:
        Dict with keys: department, category, urgency, summary.
        Falls back to defaults if extraction fails.
    """
    combined_text = "\n\n".join(
        f"Concern {i+1}: {text}" for i, text in enumerate(concern_texts) if text
    )

    if not combined_text.strip():
        return _default_analytics()

    prompt = ANALYTICS_EXTRACTION_PROMPT + combined_text

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)

        if resp.status_code != 200:
            logger.warning("Ollama returned HTTP %s for analytics extraction", resp.status_code)
            return _default_analytics()

        raw_text = resp.json().get("response", "").strip()

        # Clean markdown codeblocks if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        extracted = json.loads(raw_text)

        # Validate and sanitize
        result = {
            "department": str(extracted.get("department", "Unknown")).strip() or "Unknown",
            "category": str(extracted.get("category", "General")).strip() or "General",
            "urgency": _validate_urgency(extracted.get("urgency")),
            "summary": str(extracted.get("summary", "")).strip()[:500] or "No summary generated.",
        }

        logger.info(
            "Qwen analytics extraction: dept=%s, cat=%s, urgency=%s",
            result["department"], result["category"], result["urgency"],
        )
        return result

    except json.JSONDecodeError as e:
        logger.warning("Qwen returned non-JSON for analytics: %s", e)
        return _default_analytics()
    except Exception as e:
        logger.warning("Analytics extraction failed: %s", e)
        return _default_analytics()


def _validate_urgency(value: Any) -> str:
    """Ensure urgency is one of High/Medium/Low."""
    if isinstance(value, str) and value.strip().capitalize() in ("High", "Medium", "Low"):
        return value.strip().capitalize()
    return "Medium"


def _default_analytics() -> Dict[str, str]:
    """Fallback analytics metadata when extraction fails."""
    return {
        "department": "Unknown",
        "category": "General",
        "urgency": "Medium",
        "summary": "RFI requires manual classification.",
    }


# ── Similarity Search ─────────────────────────────────────────────────────────

def find_similar_rfis(
    supabase_client,
    embedding: List[float],
    exclude_rfi_id: str,
    threshold: float = 0.85,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search for existing RFIs with cosine similarity > threshold using pgvector.

    Uses the match_rfis stored procedure created in the migration.

    Args:
        supabase_client: Supabase client instance.
        embedding: The 384-dim embedding vector to search against.
        exclude_rfi_id: The RFI ID of the new record (to exclude self-match).
        threshold: Minimum cosine similarity (default 0.85).
        limit: Maximum number of matches to return.

    Returns:
        List of dicts with rfi_id, department, category, summary, similarity.
    """
    try:
        result = supabase_client.rpc(
            "match_rfis",
            {
                "query_embedding": embedding,
                "similarity_threshold": threshold,
                "match_count": limit,
            },
        ).execute()

        matches = []
        for row in (result.data or []):
            if row.get("rfi_id") != exclude_rfi_id:
                matches.append({
                    "rfi_id": row["rfi_id"],
                    "department": row.get("department"),
                    "category": row.get("category"),
                    "urgency": row.get("urgency"),
                    "summary": row.get("summary"),
                    "similarity": round(row.get("similarity", 0), 4),
                })

        logger.info(
            "pgvector similarity search for %s: found %d matches above %.2f",
            exclude_rfi_id, len(matches), threshold,
        )
        return matches

    except Exception as e:
        logger.warning("pgvector similarity search failed: %s", e)
        return []


# ── Full Enrichment Pipeline ─────────────────────────────────────────────────

async def enrich_rfi_analytics(
    rfi_id: str,
    concern_texts: List[str],
    supabase_client,
) -> Dict[str, Any]:
    """
    Full analytics enrichment pipeline for a newly ingested RFI.

    Steps:
      1. Extract analytics JSON via Qwen (department, category, urgency, summary)
      2. Generate embedding from the summary
      3. Update the rfi_intake row in Supabase with metadata + embedding
      4. Run similarity search to find duplicates (threshold > 0.85)
      5. Mark as duplicate if matches found, create IS_SIMILAR_TO edges in Neo4j
      6. Create Department/Category relationships in Neo4j

    Args:
        rfi_id: The RFI identifier.
        concern_texts: List of concern text strings from considerations.
        supabase_client: Supabase client instance.

    Returns:
        Dict with enrichment results including similarity matches.
    """
    from apps.backend.app.neo4j_analytics import (
        merge_analytics_metadata,
        create_similarity_edge,
    )

    # Step 1: Qwen extraction
    analytics = await extract_analytics_json(concern_texts)

    # Step 2: Generate embedding from summary
    try:
        embedding = generate_embedding(analytics["summary"])
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        embedding = None

    # Step 3: Update Supabase with analytics metadata + embedding
    update_data = {
        "department": analytics["department"],
        "category": analytics["category"],
        "urgency": analytics["urgency"],
        "summary": analytics["summary"],
    }
    if embedding:
        update_data["embedding"] = embedding

    try:
        supabase_client.table("rfi_intake").update(update_data).eq(
            "rfi_id", rfi_id
        ).execute()
        logger.info("Supabase analytics update OK for %s", rfi_id)
    except Exception as e:
        logger.warning("Supabase analytics update failed for %s: %s", rfi_id, e)

    # Step 4: Similarity search
    similar_rfis = []
    is_duplicate = False
    if embedding:
        similar_rfis = find_similar_rfis(
            supabase_client, embedding, exclude_rfi_id=rfi_id
        )
        is_duplicate = len(similar_rfis) > 0

    # Step 5: Mark duplicate and create IS_SIMILAR_TO edges
    if is_duplicate:
        try:
            supabase_client.table("rfi_intake").update(
                {"is_duplicate": True}
            ).eq("rfi_id", rfi_id).execute()
        except Exception as e:
            logger.warning("Failed to mark duplicate flag: %s", e)

        for match in similar_rfis:
            create_similarity_edge(
                source_rfi_id=rfi_id,
                target_rfi_id=match["rfi_id"],
                similarity_score=match["similarity"],
            )

    # Step 6: Create Department/Category relationships in Neo4j
    merge_analytics_metadata(
        rfi_id=rfi_id,
        department=analytics["department"],
        category=analytics["category"],
        urgency=analytics["urgency"],
        summary=analytics["summary"],
    )

    return {
        "rfi_id": rfi_id,
        "analytics": analytics,
        "embedding_generated": embedding is not None,
        "is_duplicate": is_duplicate,
        "similar_rfis": similar_rfis,
        "similar_count": len(similar_rfis),
    }
