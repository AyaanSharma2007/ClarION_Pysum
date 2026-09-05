"""
risk_router.py — Clarion Layer 4: FastAPI router for the Risk Prediction Engine
================================================================================
Exposes the risk_engine module over HTTP.  All endpoints are read-only from the
ML perspective — they call predict_with_explanation() or get_feature_schema()
and return their results.  No writes to Postgres or Neo4j happen here; this
router is purely an inference surface.

Endpoints
---------
POST /api/risk/predict    — predict RFI likelihood for a draft CTA dossier
GET  /api/risk/features   — return the feature schema (for UI form generation)
POST /api/risk/retrain    — force-retrain the model (dev/admin only)

Clarion Bible compatibility
----------------------------
- No keys from Layer 2 (Postgres/pgvector) or Layer 3 (Neo4j) are renamed.
- Phrasing throughout uses "likelihood" not "certainty" (§5, §9).
- Every response includes both 'predictions' and 'explanation' — the router
  never strips the SHAP explanation before returning it to the UI (§9 invariant).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

import sys
from pathlib import Path

# Provide fallback path resolution for local direct execution or IDEs
_BACKEND_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from apps.backend.app.api.risk_engine import (
    FEATURE_DESCRIPTIONS,
    FEATURE_NAMES,
    RFI_CATEGORIES,
    DossierFeatureVector,
    get_feature_schema,
    predict_with_explanation,
    retrain_model,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["Layer 4 — Risk Prediction Engine"])


# ---------------------------------------------------------------------------
# Request / Response schemas (Pydantic v2)
# ---------------------------------------------------------------------------

class DossierFeaturesRequest(BaseModel):
    """
    Flat feature vector for a draft CTA dossier submitted to the risk engine.
    All fields correspond 1-to-1 with FEATURE_NAMES in risk_engine.py.

    No LLM-derived fields — per Clarion Bible §5, risk prediction is an
    ML + SHAP decision, never an LLM decision.
    """

    model_config = {
        "json_schema_extra": {
            "example": {
                "trial_phase": 3,
                "therapeutic_area_oncology": True,
                "therapeutic_area_rare_disease": False,
                "product_class_biologic": True,
                "product_class_atmp": False,
                "has_section_b_protocol": True,
                "has_statistics_section": False,   # missing → high statistics RFI risk
                "has_impd_quality": True,
                "has_safety_pv_plan": True,
                "has_informed_consent": True,
                "num_mscs": 8,
                "prior_rfi_count": 2,
            }
        }
    }

    trial_phase: int = Field(
        ..., ge=1, le=4,
        description="EU CTR trial phase (1, 2, 3, or 4).",
    )
    therapeutic_area_oncology: bool = Field(
        default=False,
        description="True if therapeutic area is oncology.",
    )
    therapeutic_area_rare_disease: bool = Field(
        default=False,
        description="True if designated as orphan/rare disease.",
    )
    product_class_biologic: bool = Field(
        default=False,
        description="True if the IMP is a biologic (large molecule).",
    )
    product_class_atmp: bool = Field(
        default=False,
        description="True if the IMP is an Advanced Therapy Medicinal Product.",
    )
    has_section_b_protocol: bool = Field(
        default=True,
        description="True if Protocol Section B is present in the dossier.",
    )
    has_statistics_section: bool = Field(
        default=True,
        description="True if a Statistics section is present in the dossier.",
    )
    has_impd_quality: bool = Field(
        default=True,
        description="True if the IMPD Quality section is present.",
    )
    has_safety_pv_plan: bool = Field(
        default=True,
        description="True if a Pharmacovigilance Plan is present.",
    )
    has_informed_consent: bool = Field(
        default=True,
        description="True if an Informed Consent Form section is present.",
    )
    num_mscs: int = Field(
        default=1, ge=1, le=30,
        description="Number of Member States Concerned (1–30).",
    )
    prior_rfi_count: int = Field(
        default=0, ge=0,
        description="Historical RFI count for this sponsor/indication combination.",
    )


class CategoryLikelihood(BaseModel):
    """Per-category RFI likelihood scores. All values are in [0.0, 1.0]."""
    statistics: float = Field(description="Likelihood of a biostatistics-category RFI")
    quality_impd: float = Field(description="Likelihood of a quality/IMPD-category RFI")
    clinical_protocol: float = Field(description="Likelihood of a clinical protocol RFI")
    safety_pharmacovigilance: float = Field(description="Likelihood of a safety/PV RFI")
    regulatory_admin: float = Field(description="Likelihood of a regulatory/admin RFI")


class RiskPredictionResponse(BaseModel):
    """
    Layer 4 risk prediction response.

    INVARIANT: 'explanation' is ALWAYS present alongside 'predictions'.
    A probability score without its SHAP breakdown is architecturally
    prohibited (Clarion Bible §9 — 'No Bare Numbers').

    PHRASING INVARIANT: all values represent *likelihood*, never certainty.
    The 'disclaimer' field enforces this in every API response.
    """
    predictions: Dict[str, float] = Field(
        description=(
            "Per-category RFI likelihood scores in [0.0, 1.0]. "
            "E.g. {'statistics': 0.72} means 72% likelihood of triggering "
            "a statistics-category RFI."
        )
    )
    explanation: Dict[str, float] = Field(
        description=(
            "Flat SHAP feature attribution dict. Keys are '{feature_name}__{category}'. "
            "Positive values increase RFI likelihood; negative values decrease it. "
            "Always present — never stripped from the response."
        )
    )
    explanation_detail: Dict[str, Dict[str, float]] = Field(
        description=(
            "Full per-category SHAP breakdown. "
            "Keys are RFI category names; values are dicts of feature → SHAP weight."
        )
    )
    metadata: Dict[str, Any] = Field(
        description="Model and output semantics metadata."
    )
    disclaimer: str = Field(
        default=(
            "These are probabilistic likelihood estimates derived from an ML classifier "
            "(GradientBoostingClassifier + SHAP, Clarion Layer 4). "
            "They suggest risk — they do NOT make binding regulatory decisions. "
            "A human reviewer must evaluate all risk signals before any submission action. "
            "See Clarion Bible §5 (Decision Table) and §9 (Risk Prediction Engine)."
        ),
        description=(
            "Mandatory probabilistic disclaimer. Present on every response. "
            "Clarion Bible §9 invariant — never omit."
        ),
    )


class FeatureSchemaResponse(BaseModel):
    features: Dict[str, Any]
    rfi_categories: list
    total_features: int
    note: str


class RetrainResponse(BaseModel):
    status: str
    n_samples: int
    model_path: str
    categories: list


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/predict",
    response_model=RiskPredictionResponse,
    summary="Predict RFI likelihood for a draft CTA dossier",
    description=(
        "Submit a structured feature vector derived from a draft CTA dossier. "
        "Returns per-category RFI likelihood scores (0–1) **and** a mandatory "
        "SHAP feature explanation dict. A response without the explanation is "
        "never returned — this is enforced at the engine level, not just the API layer. "
        "\n\n"
        "**Output semantics**: values are likelihoods, not certainties. "
        "A score of 0.72 means '72% likelihood of triggering that RFI category', "
        "not 'this dossier WILL trigger an RFI'. "
        "\n\n"
        "**No LLM involvement**: prediction is purely ML + SHAP (§5, Clarion Bible)."
    ),
    response_description=(
        "RFI likelihood predictions with mandatory SHAP explanations. "
        "Both 'predictions' and 'explanation' are always present."
    ),
)
async def predict_rfi_risk(request: DossierFeaturesRequest) -> RiskPredictionResponse:
    """
    Core Layer 4 prediction endpoint.

    Passes the validated feature vector to predict_with_explanation() and
    wraps the result in a RiskPredictionResponse that includes the mandatory
    disclaimer about probabilistic phrasing.

    This endpoint never:
    - Returns predictions without an explanation (§9 invariant).
    - Uses an LLM (§5 decision table — ML + SHAP only).
    - Makes binding regulatory decisions (§0 design principle).
    """
    try:
        raw = predict_with_explanation(request.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Feature validation error: {exc}",
        ) from exc
    except RuntimeError as exc:
        # SHAP invariant violated — surface as 500 with clear message
        logger.error(
            "Clarion Layer 4: SHAP invariant violated — %s", exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Risk engine invariant error: {exc}. "
                "A prediction without its SHAP explanation cannot be returned. "
                "See Clarion Bible §9."
            ),
        ) from exc
    except Exception as exc:
        logger.error("Clarion Layer 4: Unexpected prediction error — %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk prediction failed: {exc}",
        ) from exc

    return RiskPredictionResponse(
        predictions=raw["predictions"],
        explanation=raw["explanation"],
        explanation_detail=raw["explanation_detail"],
        metadata=raw["metadata"],
        # disclaimer uses Pydantic default — always present, never omit
    )


@router.get(
    "/features",
    response_model=FeatureSchemaResponse,
    summary="Return the dossier feature schema",
    description=(
        "Returns the complete feature schema used by the risk engine, "
        "including field types, defaults, and descriptions. "
        "Consumed by the frontend to dynamically generate the dossier input form. "
        "No ML inference is performed by this endpoint."
    ),
)
async def get_risk_feature_schema() -> FeatureSchemaResponse:
    """Return the feature schema and RFI category list for UI consumption."""
    schema = get_feature_schema()
    return FeatureSchemaResponse(**schema)


@router.post(
    "/retrain",
    response_model=RetrainResponse,
    summary="Force-retrain the risk model (dev/admin only)",
    description=(
        "Drops the persisted model artefacts and retrains from a fresh synthetic "
        "calibration dataset. Intended for development cycles or after incorporating "
        "new labeled data. "
        "\n\n"
        "⚠️ This endpoint should be protected by an admin auth guard in production. "
        "In the prototype it is left open for hackathon demo convenience."
    ),
)
async def trigger_retrain(n_samples: int = 2000) -> RetrainResponse:
    """Force-retrain and reload the GBC + SHAP explainers."""
    try:
        result = retrain_model(n_samples=n_samples)
        return RetrainResponse(**result)
    except Exception as exc:
        logger.error("Clarion Layer 4: Retraining failed — %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retraining failed: {exc}",
        ) from exc
