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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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


# ── Helper: Call Gemini to draft a response ────────────────────────────────────

async def _generate_draft_with_gemini(
    concern_text: str,
    rfi_context: Dict[str, Any],
    previous_drafts: List[Dict[str, Any]],
) -> str:
    """
    Call the Gemini API to generate a regulatory response draft.
    Falls back to a template response if no API key is configured.
    """
    api_key = (GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or "").strip()
    env_model = (os.getenv("GEMINI_MODEL") or "").strip()

    if not api_key:
        logger.warning("No GEMINI_API_KEY configured — returning template draft.")
        return (
            f"In response to the authority's concern regarding: \"{concern_text[:200]}...\"\n\n"
            "The sponsor acknowledges this concern and provides the following clarification:\n\n"
            "[Draft response generated without LLM — configure GEMINI_API_KEY in your .env to enable AI drafting.]"
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

    prompt = f"""You are a senior regulatory affairs specialist drafting a sponsor response 
to an EU CTR (Clinical Trial Regulation 536/2014) validation RFI.

RFI Context:
- Member State: {country}
- Therapeutic Indication: {indication}

NCA Authority's Concern/Question:
{concern_text}
{history_context}

Instructions:
1. Draft a professional, compliant sponsor response that directly addresses the authority's concern.
2. Be specific, cite relevant regulatory sections where applicable.
3. Use formal regulatory language appropriate for EU CTR submissions.
4. The response should be concise and under 50 words.
5. If previous drafts exist, improve upon them based on their acceptance scores.

Draft the response now:"""

    gemini_models = [
        env_model,
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-pro",
        "gemini-3.5-flash",
    ]
    seen = set()
    models_to_try = [m.strip() for m in gemini_models if m and not (m.strip() in seen or seen.add(m.strip()))]

    resp = None
    last_err_detail = ""
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        logger.info("Attempting Gemini API request for model '%s'", model_name)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Successfully generated response using model '%s'", model_name)
                    break
                else:
                    last_err_detail = f"Status {resp.status_code}: {resp.text}"
                    logger.warning("Gemini model '%s' returned status %d: %s", model_name, resp.status_code, resp.text)
                    # Retry with next model on: 404 (invalid model), 503 (high demand), 429 (rate limit)
                    if resp.status_code in (404, 429, 503):
                        continue
                    else:
                        break
        except Exception as e:
            last_err_detail = str(e)
            logger.error("Gemini API call failed for model '%s': %s", model_name, e)
            continue

    if resp is None or resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to get response from Gemini API. Status: {resp.status_code if resp else 'no response'} | Details: {last_err_detail}"
        )

    res_data = resp.json()
    raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
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

    This is a heuristic-based predictor for now. It considers:
    - Length and detail of the response
    - Whether it references regulatory sections
    - Historical draft scores (if improving)

    Returns a float between 0.0 and 1.0.
    """
    score = 0.5  # Base score

    # Reward longer, more detailed responses
    word_count = len(draft_text.split())
    if word_count > 200:
        score += 0.1
    elif word_count > 100:
        score += 0.05
    elif word_count < 30:
        score -= 0.15

    # Reward references to regulatory language
    regulatory_terms = [
        "annex", "article", "section", "regulation", "eu ctr",
        "536/2014", "protocol", "amendment", "clarification",
        "evidence", "data", "compliance", "requirement"
    ]
    term_count = sum(1 for term in regulatory_terms if term.lower() in draft_text.lower())
    score += min(term_count * 0.03, 0.15)

    # Reward direct address of the concern
    concern_words = set(concern_text.lower().split())
    draft_words = set(draft_text.lower().split())
    overlap = len(concern_words & draft_words) / max(len(concern_words), 1)
    score += overlap * 0.1

    # If there are previous drafts, reward improvement
    if previous_drafts:
        prev_scores = [d.get("risk_score", 0.5) for d in previous_drafts if d.get("risk_score") is not None]
        if prev_scores:
            avg_prev = sum(prev_scores) / len(prev_scores)
            # Later drafts tend to be better
            score += 0.05

    # Add small randomness for realism
    score += random.uniform(-0.05, 0.05)

    # Clamp to [0.0, 1.0]
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

    # Step 3: No cached draft — generate via LLM
    draft_text = await _generate_draft_with_gemini(
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
