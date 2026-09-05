"""
risk_engine.py — Clarion Layer 4: Risk Prediction Engine
=========================================================
Regulatory grounding  : EU CTR 536/2014 (§9 of Clarion Bible)
Decision table row    : "Is this draft dossier likely to trigger a specific RFI
                         category?" → ML classifier (scikit-learn) + SHAP
                         (Clarion Bible §5, immutable decision table)

Architectural invariants enforced here
---------------------------------------
1. NO BARE NUMBERS  — predict_with_explanation() raises RuntimeError before
   returning a dict that lacks its 'explanation' key.  A probability score
   without its SHAP breakdown is unreachable by construction.
2. NO CERTAINTY PHRASING — output uses 'likelihood' keys, never 'guaranteed'
   or 'certain'.  Docstrings mirror this language.
3. NO LLM RISK EVALUATION — zero LLM calls in this module.  Pure
   scikit-learn + SHAP pipeline, as required by §5.
4. SHAP on every prediction — TreeExplainer is instantiated once at module
   load (shared singleton); shap_values are computed fresh per call so they
   are always specific to the input dossier.
5. Probabilistic, never deterministic output — all return values are floats
   in [0.0, 1.0] representing *likelihood*, not verdicts.

Clarion Bible §15 compatibility
---------------------------------
No schema keys from Layer 2 (Postgres/pgvector) or Layer 3 (Neo4j) are
renamed or removed.  consideration_id, rfi_id, owner_team, msc_id are
untouched.  This module is purely additive.
"""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import shap
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — model artefacts live next to the backend, not in-tree with source
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # apps/backend/
_ARTIFACTS_DIR = _BACKEND_ROOT / "model_artifacts"
_MODEL_PATH = _ARTIFACTS_DIR / "risk_model.joblib"
_EXPLAINER_PATH = _ARTIFACTS_DIR / "risk_explainer.joblib"

# ---------------------------------------------------------------------------
# RFI risk categories
# Derived from §1.1 Regulatory Citation Map and §5 Decision Table.
# Any new category must first be added as a row in §5 of the Clarion Bible
# before being added here (Bible rule §15 §5).
# ---------------------------------------------------------------------------
RFI_CATEGORIES: List[str] = [
    "statistics",             # Biostatistics / sample size / primary endpoint
    "quality_impd",           # IMPD quality completeness
    "clinical_protocol",      # Protocol design / missing required sections
    "safety_pharmacovigilance",  # Safety data / PV plan completeness
    "regulatory_admin",       # Administrative / format / submission completeness
]

# ---------------------------------------------------------------------------
# Feature schema
# Every feature is structural dossier metadata — fully deterministic, no LLM.
# ---------------------------------------------------------------------------
FEATURE_NAMES: List[str] = [
    "trial_phase",                    # int  1–4  (EU CTR trial phase)
    "therapeutic_area_oncology",      # bool — oncology flag (elevated baseline RFI rate)
    "therapeutic_area_rare_disease",  # bool — orphan/rare disease
    "product_class_biologic",         # bool — biologic IMP
    "product_class_atmp",             # bool — advanced therapy medicinal product
    "has_section_b_protocol",         # bool — Protocol Section B present
    "has_statistics_section",         # bool — Statistics section present
    "has_impd_quality",               # bool — IMPD quality section present
    "has_safety_pv_plan",             # bool — Pharmacovigilance plan present
    "has_informed_consent",           # bool — Informed Consent Form section present
    "num_mscs",                       # int  — number of Member States Concerned
    "prior_rfi_count",                # int  — historical RFI count for same sponsor/indication
]

FEATURE_DESCRIPTIONS: Dict[str, str] = {
    "trial_phase": "EU CTR trial phase (1, 2, 3, or 4)",
    "therapeutic_area_oncology": "True if the therapeutic area is oncology",
    "therapeutic_area_rare_disease": "True if designated as orphan/rare disease",
    "product_class_biologic": "True if the IMP is a biologic (large molecule)",
    "product_class_atmp": "True if the IMP is an Advanced Therapy Medicinal Product",
    "has_section_b_protocol": "True if Protocol Section B is present in the dossier",
    "has_statistics_section": "True if a Statistics section is present in the dossier",
    "has_impd_quality": "True if the IMPD Quality section is present",
    "has_safety_pv_plan": "True if a Pharmacovigilance Plan is present",
    "has_informed_consent": "True if an Informed Consent Form section is present",
    "num_mscs": "Number of Member State Concerned countries in this submission",
    "prior_rfi_count": "Number of historical RFIs for this sponsor/indication combination",
}


# ---------------------------------------------------------------------------
# Typed feature vector — Pydantic-free dataclass for internal pipeline use.
# The FastAPI layer (risk_router.py) owns the Pydantic Request/Response models.
# ---------------------------------------------------------------------------
@dataclass
class DossierFeatureVector:
    """
    Structured feature vector derived from a draft CTA dossier.

    All fields are structural dossier metadata (trial phase, product class,
    section presence/absence). No LLM-derived fields — per §5 of the Clarion
    Bible, risk prediction is an ML + SHAP decision, never an LLM decision.
    """
    trial_phase: int = 1
    therapeutic_area_oncology: bool = False
    therapeutic_area_rare_disease: bool = False
    product_class_biologic: bool = False
    product_class_atmp: bool = False
    has_section_b_protocol: bool = True
    has_statistics_section: bool = True
    has_impd_quality: bool = True
    has_safety_pv_plan: bool = True
    has_informed_consent: bool = True
    num_mscs: int = 1
    prior_rfi_count: int = 0

    def to_array(self) -> np.ndarray:
        """Return feature values as a numpy array in FEATURE_NAMES order."""
        d = asdict(self)
        return np.array([d[f] for f in FEATURE_NAMES], dtype=float)

    @classmethod
    def from_dict(cls, raw: dict) -> "DossierFeatureVector":
        """
        Build a DossierFeatureVector from an arbitrary dict, validating types
        and raising ValueError on missing required keys.
        """
        known = {f.name for f in fields(cls)}
        missing = [k for k in FEATURE_NAMES if k not in raw]
        if missing:
            raise ValueError(
                f"Missing required dossier feature(s): {missing}. "
                f"All FEATURE_NAMES must be present in the input dict."
            )
        extra = {k: v for k, v in raw.items() if k in known}
        return cls(**extra)


# ---------------------------------------------------------------------------
# Synthetic calibration dataset
# §14.1 — prototype runs on synthetic data mirroring Novo Nordisk's mix.
# Real CTA/RFI content is never used at hackathon stage.
# Labels generated with domain-realistic rules (not random).
# ---------------------------------------------------------------------------

def _generate_synthetic_dataset(n_samples: int = 2000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate a synthetic CTA dossier dataset calibrated to Novo Nordisk's
    stated submission profile (650 CTAs/year, Phase 1–3 heavy, oncology +
    diabetes prominent, ~30 EEA countries).

    Label rules (simplified domain heuristics, not real clinical data):
    - statistics     : high if phase >= 3 AND missing statistics section
    - quality_impd   : high if biologic/ATMP AND missing IMPD quality
    - clinical_protocol : high if missing section B
    - safety_pv      : high if missing PV plan OR rare disease without safety section
    - regulatory_admin  : high for multi-MSC + missing consent
    """
    rng = np.random.default_rng(seed)
    n = n_samples

    # --- Feature sampling ---
    trial_phase = rng.choice([1, 2, 3, 4], size=n, p=[0.25, 0.30, 0.38, 0.07])
    ta_onco = rng.random(n) < 0.35
    ta_rare = rng.random(n) < 0.18
    pc_bio = rng.random(n) < 0.28
    pc_atmp = rng.random(n) < 0.07
    has_sec_b = rng.random(n) > 0.12       # 12% missing — realistic gap rate
    has_stats = rng.random(n) > 0.15
    has_impd = rng.random(n) > 0.10
    has_pv = rng.random(n) > 0.11
    has_icf = rng.random(n) > 0.08
    num_mscs = rng.integers(1, 31, size=n)
    prior_rfis = rng.integers(0, 8, size=n)

    X = np.column_stack([
        trial_phase, ta_onco, ta_rare, pc_bio, pc_atmp,
        has_sec_b, has_stats, has_impd, has_pv, has_icf,
        num_mscs, prior_rfis,
    ]).astype(float)

    # --- Label generation (domain-realistic, calibrated) ---
    def _sigmoid(z): return 1 / (1 + np.exp(-z))

    # statistics RFI: Phase 3+, no stats section, oncology adds complexity
    z_stats = (
        0.9 * (trial_phase >= 3)
        - 1.8 * has_stats
        + 0.5 * ta_onco
        + 0.3 * prior_rfis
        - 0.5
    )
    y_stats = (rng.random(n) < _sigmoid(z_stats)).astype(int)

    # quality_impd RFI: biologic/ATMP without IMPD quality section
    z_qual = (
        1.2 * (pc_bio | pc_atmp)
        - 2.0 * has_impd
        + 0.4 * prior_rfis
        - 0.3
    )
    y_qual = (rng.random(n) < _sigmoid(z_qual)).astype(int)

    # clinical_protocol RFI: missing section B is a primary trigger
    z_clin = (
        - 2.2 * has_sec_b
        + 0.6 * (trial_phase >= 2)
        + 0.3 * ta_rare
        + 0.2 * prior_rfis
        + 0.4
    )
    y_clin = (rng.random(n) < _sigmoid(z_clin)).astype(int)

    # safety_pv RFI: missing PV plan, rare disease elevates baseline
    z_safe = (
        - 2.0 * has_pv
        + 0.8 * ta_rare
        + 0.5 * pc_atmp
        + 0.3 * prior_rfis
        - 0.1
    )
    y_safe = (rng.random(n) < _sigmoid(z_safe)).astype(int)

    # regulatory_admin RFI: multi-MSC + missing ICF is the classic trigger
    z_admin = (
        0.04 * num_mscs
        - 1.5 * has_icf
        + 0.2 * prior_rfis
        - 0.8
    )
    y_admin = (rng.random(n) < _sigmoid(z_admin)).astype(int)

    Y: np.ndarray = np.column_stack([y_stats, y_qual, y_clin, y_safe, y_admin]).astype(int)
    return X, Y


# ---------------------------------------------------------------------------
# Model training & persistence
# ---------------------------------------------------------------------------

def _train_and_persist_model() -> tuple:
    """
    Train one GradientBoostingClassifier per RFI category (via
    MultiOutputClassifier) and persist the model + explainer to disk.
    Returns (model, explainer).
    """
    logger.info(
        "Clarion Layer 4: No persisted model found. "
        "Training on synthetic calibration dataset (n=2000). "
        "See §14.1 of Clarion Bible — synthetic data is the correct prototype behaviour."
    )
    X, Y = _generate_synthetic_dataset(n_samples=2000)

    base_gbc = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        min_samples_leaf=10,
        random_state=42,
    )
    model = MultiOutputClassifier(base_gbc, n_jobs=-1)
    model.fit(X, Y)  # type: ignore

    # Build one TreeExplainer per output estimator — SHAP requires per-estimator
    # access for MultiOutputClassifier because each output has its own tree.
    explainers = [
        shap.TreeExplainer(est) for est in model.estimators_
    ]

    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _MODEL_PATH)
    joblib.dump(explainers, _EXPLAINER_PATH)
    logger.info("Clarion Layer 4: Model and explainers persisted to %s", _ARTIFACTS_DIR)
    return model, explainers


def _load_or_train() -> tuple:
    """Return (model, explainers), loading from disk if available or training fresh."""
    if _MODEL_PATH.exists() and _EXPLAINER_PATH.exists():
        logger.info("Clarion Layer 4: Loading persisted model from %s", _MODEL_PATH)
        model = joblib.load(_MODEL_PATH)
        explainers = joblib.load(_EXPLAINER_PATH)
        return model, explainers
    return _train_and_persist_model()


# ---------------------------------------------------------------------------
# Module-level singletons — loaded once at import time.
# Never re-instantiate per-request; SHAP values are computed fresh each call.
# ---------------------------------------------------------------------------
_risk_model, _explainers = _load_or_train()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict_with_explanation(dossier_features: dict) -> dict:
    """
    Predict the likelihood of each RFI category being triggered by this draft
    CTA dossier, accompanied by a mandatory SHAP feature explanation.

    Parameters
    ----------
    dossier_features : dict
        Flat dict with keys matching FEATURE_NAMES exactly.  Use
        DossierFeatureVector.from_dict() to validate types before calling here.

    Returns
    -------
    dict with two guaranteed top-level keys:
        {
            "predictions": {
                "statistics": 0.72,          # float in [0.0, 1.0]
                "quality_impd": 0.15,
                "clinical_protocol": 0.43,
                "safety_pharmacovigilance": 0.29,
                "regulatory_admin": 0.11
            },
            "explanation": {
                "missing_section_b_protocol": +0.35,   # positive = increases risk
                "phase_3_complexity": +0.22,            # named for readability
                ...  # one entry per FEATURE_NAMES, per predicted category
            }
        }

    Raises
    ------
    ValueError
        If required feature keys are missing from dossier_features.
    RuntimeError
        If SHAP value computation fails — a bare 'predictions' dict without
        its 'explanation' is architecturally prohibited (Clarion Bible §9).

    Notes
    -----
    - Output is ALWAYS probabilistic.  Never say "will trigger"; always say
      "likelihood of triggering".  This invariant is enforced at the API
      layer (risk_router.py) and documented here so it cannot silently erode.
    - SHAP values are signed: positive = feature increases RFI likelihood,
      negative = feature decreases it.
    - This function contains zero LLM calls.  Risk prediction is a
      deterministic ML + SHAP operation per §5 of the Clarion Bible.
    """
    # 1. Validate and build the feature vector
    fv = DossierFeatureVector.from_dict(dossier_features)
    x = fv.to_array().reshape(1, -1)  # shape (1, n_features)

    # 2. Per-category probability predictions
    #    MultiOutputClassifier.predict_proba returns a list of (n_samples, 2)
    #    arrays — one per output.  We take index [1] = P(class=1).
    proba_list = _risk_model.predict_proba(x)
    predictions: Dict[str, float] = {}
    for cat, proba_arr in zip(RFI_CATEGORIES, proba_list):
        predictions[cat] = float(round(proba_arr[0, 1], 4))

    # 3. SHAP explanations — one explainer per category estimator.
    #    We aggregate across categories into a single explanation dict,
    #    labelling each feature+category pair for full inspectability.
    #    The "explanation" key in the output is flat for UI compatibility
    #    but the full per-category breakdown is preserved in
    #    "explanation_detail" for deeper tooling.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # suppress SHAP tree approximation warnings
        try:
            shap_per_category: Dict[str, Dict[str, float]] = {}
            for cat, explainer in zip(RFI_CATEGORIES, _explainers):
                sv = explainer.shap_values(x)
                # TreeExplainer for GBC returns shape (n_samples, n_features)
                # or (n_samples, n_features) for binary.  Normalise:
                if isinstance(sv, list):
                    # Binary GBC: sv is [shap_for_class0, shap_for_class1]
                    sv_row = sv[1][0]   # class=1 (RFI triggered) SHAP values
                else:
                    sv_row = sv[0]

                shap_per_category[cat] = {
                    feat: round(float(val), 6)
                    for feat, val in zip(FEATURE_NAMES, sv_row)
                }
        except Exception as exc:
            # Hard fail — never return predictions without explanation.
            # This is the architectural invariant from Clarion Bible §9:
            # "probabilistic outputs without explainability features are unacceptable."
            raise RuntimeError(
                f"Clarion Layer 4 INVARIANT VIOLATED: SHAP computation failed. "
                f"Cannot return a prediction without its explanation. "
                f"Original error: {exc}"
            ) from exc

    # 4. Build the flat explanation dict (highest-magnitude feature per
    #    category, for the primary output used by the UI).
    #    The full per-category breakdown is in explanation_detail.
    flat_explanation: Dict[str, float] = {}
    for cat, feat_map in shap_per_category.items():
        for feat, val in feat_map.items():
            key = f"{feat}__{cat}"
            flat_explanation[key] = val

    # 5. Verify the invariant before returning: both keys must be present.
    result = {
        "predictions": predictions,
        "explanation": flat_explanation,
        "explanation_detail": shap_per_category,
        "metadata": {
            "categories": RFI_CATEGORIES,
            "feature_names": FEATURE_NAMES,
            "model_type": "GradientBoostingClassifier (MultiOutputClassifier)",
            "explainability": "SHAP TreeExplainer",
            "output_semantics": (
                "All values in 'predictions' are likelihoods in [0.0, 1.0]. "
                "Positive SHAP values in 'explanation' increase RFI likelihood; "
                "negative values decrease it. "
                "These are probabilistic estimates — they suggest risk, "
                "they do NOT make binding regulatory decisions. "
                "See Clarion Bible §5 and §9."
            ),
        },
    }

    # Final invariant guard — defensive, belt-and-suspenders
    assert "predictions" in result and "explanation" in result, (
        "Clarion Layer 4: BUG — result dict is missing required keys. "
        "This is an invariant violation. Report immediately."
    )

    return result


def get_feature_schema() -> dict:
    """
    Return the complete feature schema used by the risk engine.
    Consumed by GET /api/risk/features to drive UI form generation.
    """
    schema = {}
    fv_fields = {f.name: f for f in fields(DossierFeatureVector)}
    for fname in FEATURE_NAMES:
        f = fv_fields[fname]
        schema[fname] = {
            "type": f.type if isinstance(f.type, str) else f.type.__name__,
            "default": f.default,
            "description": FEATURE_DESCRIPTIONS[fname],
        }
    return {
        "features": schema,
        "rfi_categories": RFI_CATEGORIES,
        "total_features": len(FEATURE_NAMES),
        "note": (
            "All features are structural dossier metadata. "
            "No LLM-derived features — per Clarion Bible §5."
        ),
    }


def retrain_model(n_samples: int = 2000) -> dict:
    """
    Force-retrain the model on a fresh synthetic dataset and reload singletons.
    Intended for use during development / after incorporating new labeled data.

    Returns a summary dict confirming retraining completed.
    """
    global _risk_model, _explainers
    # Remove stale artefacts so _train_and_persist_model always re-trains
    for p in [_MODEL_PATH, _EXPLAINER_PATH]:
        if p.exists():
            p.unlink()

    _risk_model, _explainers = _train_and_persist_model()
    return {
        "status": "retrained",
        "n_samples": n_samples,
        "model_path": str(_MODEL_PATH),
        "categories": RFI_CATEGORIES,
    }
