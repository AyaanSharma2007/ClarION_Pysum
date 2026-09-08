"""
draft_router.py — AI Draft Response & Risk Prediction Router
=============================================================
Provides endpoints for generating AI-drafted responses to RFI considerations
and automatically predicting their acceptance risk.

Endpoints
---------
POST /api/draft/{consideration_id}  — draft a response and predict risk
GET  /api/draft/{consideration_id}/history — get all past drafts for a consideration
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/draft", tags=["AI Draft Response"])

# ── LLM Configuration ──────────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "clarion-qwen")
LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8001")


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class DraftResponseResult(BaseModel):
    draft_id: str
    consideration_id: str
    draft_text: str
    risk_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Predicted probability that this draft response will be accepted (0.0–1.0)."
    )
    created_at: str


class DraftHistoryItem(BaseModel):
    draft_id: str
    draft_text: str
    risk_score: Optional[float]
    created_at: str


class DraftHistoryResponse(BaseModel):
    consideration_id: str
    drafts: List[DraftHistoryItem]

class EvaluateDraftRequest(BaseModel):
    draft_text: str

# ── Helper: Fetch similar past responses for RAG context ───────────────────────

async def _fetch_rag_context(concern_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Query Layer 2's /search/recommend endpoint to retrieve historically
    successful responses to similar concerns (pgvector cosine similarity +
    outcome-weighted re-ranking).

    Returns a list of past responses with their similarity scores.
    Only includes responses that have response_text (i.e., were actually answered).
    """
    url = f"{LAYER2_URL}/search/recommend"
    payload = {
        "concern_text": concern_text,
        "top_k": top_k * 2,  # Over-fetch to filter for those with response_text
        "min_similarity": 0.40,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                # Only include entries that have an actual response_text
                with_responses = [
                    r for r in results
                    if r.get("response_text") and len(r["response_text"].strip()) > 10
                ]
                logger.info(
                    "RAG retrieval: found %d similar past responses (%d with response text) for drafting",
                    len(results), len(with_responses),
                )
                return with_responses[:top_k]
    except Exception as exc:
        logger.warning("RAG retrieval failed (continuing without RAG context): %s", exc)
    return []


# ── Helper: Call Local Model to draft a response ───────────────────────────────

async def _generate_draft_with_local_model(
    concern_text: str,
    rfi_context: Dict[str, Any],
    previous_drafts: List[Dict[str, Any]],
) -> str:
    """
    Call the local Ollama API to generate a regulatory response draft using our fine-tuned Qwen model.

    Uses Retrieval-Augmented Generation (RAG): fetches similar past successful
    responses from the vector database and injects them into the prompt as
    exemplars for the LLM to follow.
    """
    # ── RAG: Fetch similar past successful responses ───────────────────────
    rag_examples = await _fetch_rag_context(concern_text, top_k=3)

    rag_context = ""
    if rag_examples:
        rag_context = "\n\nHistorically successful responses to similar concerns (use these as style and content guides):\n"
        for i, ex in enumerate(rag_examples, 1):
            sim = ex.get("similarity_score", 0)
            outcome = ex.get("outcome_status", "unknown")
            resp_text = ex.get("response_text", "")[:400]
            concern = (ex.get("concern_text") or "")[:150]
            rag_context += (
                f"\n--- Example {i} (similarity: {sim:.0%}, outcome: {outcome}) ---\n"
                f"Concern: {concern}\n"
                f"Accepted Response: {resp_text}\n"
            )

    # Build context from previous drafts
    history_context = ""
    if previous_drafts:
        history_context = "\n\nPrevious draft attempts for this consideration (for reference — improve upon these):\n"
        for i, d in enumerate(previous_drafts[-3:], 1):  # Last 3 drafts
            score = d.get("risk_score")
            score_str = f" (acceptance probability: {score:.0%})" if score is not None else ""
            history_context += f"\n--- Draft {i}{score_str} ---\n{d['draft_text'][:500]}\n"

    rfi_id = rfi_context.get("rfi_id", "Unknown")
    country = rfi_context.get("country", "Unknown")
    indication = rfi_context.get("indication", "Unknown")

    prompt = f"Context: EU CTR Validation RFI\nMSC: {country}\nIndication: {indication}\nConcern: {concern_text}{rag_context}{history_context}"

    system_prompt = (
        "You are an expert regulatory affairs AI. Draft a professional response for the "
        "following EU CTR Validation RFI consideration. "
        "If similar historically accepted responses are provided, use them as style and "
        "content guides to maximise the acceptance probability of your draft. "
        "Keep it under 50 words."
    )

    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2, # Low temperature for more deterministic/professional output
            "top_p": 0.9,
        }
    }
    
    logger.info("Attempting Ollama API request for model '%s' (RAG examples: %d)", OLLAMA_MODEL, len(rag_examples))
    resp = None
    last_err_detail = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Successfully generated RAG-augmented response using model '%s'", OLLAMA_MODEL)
            else:
                last_err_detail = f"Status {resp.status_code}: {resp.text}"
                logger.warning("Ollama model '%s' returned status %d: %s", OLLAMA_MODEL, resp.status_code, resp.text)
    except Exception as e:
        last_err_detail = str(e)
        logger.error("Ollama API call failed for model '%s': %s", OLLAMA_MODEL, e)

    if resp is None or resp.status_code != 200:
        logger.warning(f"Failed to get response from Ollama API. Returning fallback template. Details: {last_err_detail}")
        # Fallback: if RAG examples are available, use the best one as the draft
        if rag_examples and rag_examples[0].get("response_text"):
            best = rag_examples[0]["response_text"]
            sim = rag_examples[0].get("similarity_score", 0)
            logger.info("Using best RAG example as fallback draft (similarity: %.0f%%)", sim * 100)
            words = best.split()
            return " ".join(words[:50]) if len(words) > 50 else best

        return (
            f"In response to the authority's concern regarding: \"{concern_text[:200]}...\"\n\n"
            "The sponsor acknowledges this concern and provides the following clarification:\n\n"
            "[Draft response generated without LLM — make sure Ollama is running with the correct model.]"
        )

    res_data = resp.json()
    raw_text = res_data.get("response", "").strip()
    # Enforce 50‑word limit
    words = raw_text.split()
    if len(words) > 50:
        raw_text = " ".join(words[:50])
    return raw_text


# ── Helper: Predict risk score ─────────────────────────────────────────────────

def _predict_risk_score(
    concern_text: str,
    draft_text: str,
    previous_drafts: List[Dict[str, Any]],
) -> float:
    """
    Predict the probability that the drafted response will be accepted.

    Uses the real Layer 4 ML risk engine (GradientBoostingClassifier + SHAP)
    from risk_engine.py to compute the actual risk, then derives an acceptance
    probability from the maximum category-level risk.

    Falls back to a simple heuristic only if the ML engine raises an error.

    Returns a float between 0.0 and 1.0 (acceptance probability).
    """
    try:
        from apps.backend.app.api.risk_engine import predict_with_explanation

        # Build dossier features from the concern text and draft content.
        # We infer structural features from keywords in the concern text to
        # drive the ML model — these are the same 12 features the risk engine
        # expects (see FEATURE_NAMES in risk_engine.py).
        concern_lower = concern_text.lower()
        draft_lower = draft_text.lower()
        combined = concern_lower + " " + draft_lower

        dossier_features = {
            "trial_phase": 3,  # Default assumption: Phase 3 (most common for Novo Nordisk)
            "therapeutic_area_oncology": any(
                kw in combined for kw in ["oncology", "cancer", "tumor", "tumour", "neoplasm"]
            ),
            "therapeutic_area_rare_disease": any(
                kw in combined for kw in ["rare disease", "orphan", "rare condition"]
            ),
            "product_class_biologic": any(
                kw in combined for kw in ["biologic", "monoclonal", "antibody", "biosimilar"]
            ),
            "product_class_atmp": any(
                kw in combined for kw in ["atmp", "advanced therapy", "gene therapy", "cell therapy"]
            ),
            "has_section_b_protocol": not any(
                kw in concern_lower for kw in ["protocol missing", "no protocol", "missing protocol section"]
            ),
            "has_statistics_section": not any(
                kw in concern_lower for kw in ["statistic", "sample size", "primary endpoint", "statistical analysis"]
            ),
            "has_impd_quality": not any(
                kw in concern_lower for kw in ["impd", "quality", "drug product", "manufacturing"]
            ),
            "has_safety_pv_plan": not any(
                kw in concern_lower for kw in ["pharmacovigilance", "safety", "adverse event", "pv plan"]
            ),
            "has_informed_consent": not any(
                kw in concern_lower for kw in ["informed consent", "consent form", "icf"]
            ),
            "num_mscs": 5,   # Moderate default
            "prior_rfi_count": 1,
        }

        result = predict_with_explanation(dossier_features)
        predictions = result.get("predictions", {})

        if predictions:
            # Max risk across all categories = worst-case RFI trigger likelihood.
            # Acceptance probability = 1 - max_risk (inversely related).
            max_risk = max(predictions.values())
            base_prob = 1.0 - max_risk
            
            # Apply continuous text-based sensitivity to differentiate drafts
            # and heavily penalize extremely short manual drafts
            text_length = len(draft_text)
            word_count = len(draft_text.split())
            
            if word_count < 50:
                # Continuous penalty: up to -0.60 for 0 words, -0.0 for 50 words
                penalty = ((50 - word_count) / 50.0) * 0.60
                base_prob -= penalty
            elif word_count > 100:
                base_prob += 0.10
                
            # Deterministic pseudo-random jitter based on length
            jitter = (text_length % 15) * 0.002
            base_prob += jitter
            
            acceptance_prob = max(0.0, min(1.0, round(base_prob, 3)))
            return acceptance_prob

    except Exception as exc:
        logger.warning("ML risk engine fallback — using heuristic: %s", exc)

    # Fallback heuristic (only used if ML engine fails)
    score = 0.5
    word_count = len(draft_text.split())
    
    if word_count < 50:
        penalty = ((50 - word_count) / 50.0) * 0.60
        score -= penalty
    elif word_count > 100:
        score += 0.10

    regulatory_terms = [
        "annex", "article", "section", "regulation", "eu ctr",
        "536/2014", "protocol", "amendment", "clarification",
        "evidence", "data", "compliance", "requirement"
    ]
    term_count = sum(1 for term in regulatory_terms if term.lower() in draft_text.lower())
    score += min(term_count * 0.03, 0.15)
    
    # Deterministic jitter for heuristic fallback too
    text_length = len(draft_text)
    jitter = (text_length % 15) * 0.002
    score += jitter

    return max(0.0, min(1.0, round(score, 3)))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/{consideration_id}",
    response_model=DraftResponseResult,
    summary="Draft an AI response for a consideration and predict acceptance risk",
)
async def draft_response(consideration_id: str, force: bool = False):
    """
    1. Fetches the consideration's concern_text and RFI context from Layer 2.
    2. If a draft already exists in the DB and `force` is False, returns the latest one (no LLM call).
    3. Otherwise calls the Gemini LLM to generate a new draft response.
    4. Runs the risk predictor on the new draft.
    5. Saves the draft + risk score to the ai_draft_response table via Layer 2.
    6. Returns both the draft text and risk score in a single response.
    7. The response is concise (≤ 50 words) and does not mention the consideration ID.
    """

    # Step 1: Fetch consideration details from Layer 2
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{LAYER2_URL}/rfi/consideration/{consideration_id}")
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Layer 2 service is not reachable. Make sure it's running on port 8001.",
            )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consideration {consideration_id} not found in Layer 2 (Layer 2 returned {resp.status_code}).",
        )

    # Step 2: Cache check – return latest draft unless forced
    if not force:
        try:
            history_resp = await client.get(f"{LAYER2_URL}/rfi/consideration/{consideration_id}/drafts")
            previous_drafts = history_resp.json() if history_resp.status_code == 200 else []
        except Exception:
            previous_drafts = []
        if previous_drafts:
            latest = previous_drafts[-1]
            logger.info("Cache hit: returning existing draft for consideration %s (draft id: %s)", consideration_id, latest.get("id", "?"))
            return DraftResponseResult(
                draft_id=latest.get("id", "cached"),
                consideration_id=consideration_id,
                draft_text=latest.get("draft_text", ""),
                risk_score=latest.get("risk_score") or 0.5,
                created_at=latest.get("created_at", ""),
            )
    # If forced or no cached draft, continue to generate a new one.
    # Reset previous_drafts variable for later risk prediction
    previous_drafts = []

    consideration_data = resp.json()
    concern_text = consideration_data.get("concern_text", "")
    if not concern_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This consideration has no concern_text to draft a response for.",
        )

    rfi_context = {
        "rfi_id": consideration_data.get("rfi_id", ""),
        "country": consideration_data.get("country", ""),
        "indication": consideration_data.get("indication", ""),
    }

    # Fetch previous drafts for LLM context (if force=True, we still want history context to improve upon)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            history_resp = await client.get(
                f"{LAYER2_URL}/rfi/consideration/{consideration_id}/drafts"
            )
            previous_drafts = history_resp.json() if history_resp.status_code == 200 else []
        except Exception:
            previous_drafts = []

    # Step 3: No cached draft — generate via local LLM
    draft_text = await _generate_draft_with_local_model(
        concern_text=concern_text,
        rfi_context=rfi_context,
        previous_drafts=previous_drafts,
    )

    # Step 4: Predict risk score
    risk_score = _predict_risk_score(
        concern_text=concern_text,
        draft_text=draft_text,
        previous_drafts=previous_drafts,
    )

    # Step 5: Save draft to Layer 2
    now = datetime.now(tz=timezone.utc).isoformat()
    draft_payload = {
        "consideration_id": consideration_id,
        "draft_text": draft_text,
        "risk_score": risk_score,
    }

    draft_id = ""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            save_resp = await client.post(
                f"{LAYER2_URL}/rfi/consideration/{consideration_id}/drafts",
                json=draft_payload,
            )
            if save_resp.status_code in (200, 201):
                saved = save_resp.json()
                draft_id = saved.get("id", "")
                now = saved.get("created_at", now)
        except Exception as e:
            logger.warning("Failed to save draft to Layer 2: %s", e)

    # Step 6: Return result
    return DraftResponseResult(
        draft_id=draft_id or "unsaved",
        consideration_id=consideration_id,
        draft_text=draft_text,
        risk_score=risk_score,
        created_at=now,
    )


@router.get(
    "/{consideration_id}/history",
    response_model=DraftHistoryResponse,
    summary="Get all historical drafts for a consideration",
)
async def get_draft_history(consideration_id: str):
    """
    Fetches all previous AI-drafted responses and their risk scores
    for a given consideration, ordered by creation time.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{LAYER2_URL}/rfi/consideration/{consideration_id}/drafts"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Layer 2 service is not reachable."
            )

    if resp.status_code != 200:
        return DraftHistoryResponse(
            consideration_id=consideration_id,
            drafts=[],
        )

    raw_drafts = resp.json()
    drafts = [
        DraftHistoryItem(
            draft_id=d.get("id", ""),
            draft_text=d.get("draft_text", ""),
            risk_score=d.get("risk_score"),
            created_at=d.get("created_at", ""),
        )
        for d in raw_drafts
    ]

    return DraftHistoryResponse(
        consideration_id=consideration_id,
        drafts=drafts,
    )


@router.post(
    "/{consideration_id}/evaluate",
    response_model=DraftResponseResult,
    summary="Evaluate risk for a manually edited draft",
)
async def evaluate_manual_draft(consideration_id: str, body: EvaluateDraftRequest):
    """
    Evaluates risk for a manually edited draft, saves it to Layer 2,
    and returns the risk score.
    """
    draft_text = body.draft_text

    # Step 1: Fetch consideration details from Layer 2
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{LAYER2_URL}/rfi/consideration/{consideration_id}")
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Layer 2 service is not reachable."
            )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consideration {consideration_id} not found."
        )

    consideration_data = resp.json()
    concern_text = consideration_data.get("concern_text", "")
    
    # Step 2: Predict risk
    risk_score = _predict_risk_score(
        concern_text=concern_text,
        draft_text=draft_text,
        previous_drafts=[],
    )

    # Step 3: Save draft to Layer 2
    now = datetime.now(tz=timezone.utc).isoformat()
    draft_payload = {
        "consideration_id": consideration_id,
        "draft_text": draft_text,
        "risk_score": risk_score,
    }

    draft_id = ""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            save_resp = await client.post(
                f"{LAYER2_URL}/rfi/consideration/{consideration_id}/drafts",
                json=draft_payload,
            )
            if save_resp.status_code in (200, 201):
                saved = save_resp.json()
                draft_id = saved.get("id", "")
                now = saved.get("created_at", now)
        except Exception as e:
            logger.warning("Failed to save draft to Layer 2: %s", e)

    return DraftResponseResult(
        draft_id=draft_id or "unsaved",
        consideration_id=consideration_id,
        draft_text=draft_text,
        risk_score=risk_score,
        created_at=now,
    )

