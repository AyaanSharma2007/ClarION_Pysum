"""
retrain_risk_model.py — Continuous Learning Pipeline for Clarion Layer 4
========================================================================
Pulls completed RFIs from Layer 2, extracts structural features from their
concern_text and response_text, and retrains the GradientBoostingClassifier
used by the risk prediction engine.

Usage:
    python scripts/retrain_risk_model.py

The script:
1. Fetches all RFIs from Layer 2 (GET /rfi).
2. Filters for terminal-state RFIs (status = 'submitted') with response text.
3. Extracts the same 12 structural features used by risk_engine.py.
4. Derives ground-truth labels from whether each consideration's concern text
   relates to one of the 5 RFI risk categories (statistics, quality_impd,
   clinical_protocol, safety_pharmacovigilance, regulatory_admin).
5. Augments with synthetic calibration data to avoid overfitting on small datasets.
6. Trains a new MultiOutputClassifier(GradientBoostingClassifier) + SHAP explainers.
7. Persists the model to apps/backend/model_artifacts/risk_model.joblib.
8. Prints a summary report.

The risk engine hot-reloads the model on the next API restart, or can be
triggered via the POST /api/risk/retrain endpoint.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx
import joblib
import numpy as np
import shap
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.multioutput import MultiOutputClassifier

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8001")
ARTIFACTS_DIR = PROJECT_ROOT / "apps" / "backend" / "model_artifacts"
MODEL_PATH = ARTIFACTS_DIR / "risk_model.joblib"
EXPLAINER_PATH = ARTIFACTS_DIR / "risk_explainer.joblib"

RFI_CATEGORIES = [
    "statistics",
    "quality_impd",
    "clinical_protocol",
    "safety_pharmacovigilance",
    "regulatory_admin",
]

FEATURE_NAMES = [
    "trial_phase",
    "therapeutic_area_oncology",
    "therapeutic_area_rare_disease",
    "product_class_biologic",
    "product_class_atmp",
    "has_section_b_protocol",
    "has_statistics_section",
    "has_impd_quality",
    "has_safety_pv_plan",
    "has_informed_consent",
    "num_mscs",
    "prior_rfi_count",
]

# ── Category keyword detectors ─────────────────────────────────────────────────
# These map concern text keywords to ground-truth RFI category labels.

CATEGORY_KEYWORDS = {
    "statistics": [
        "statistic", "sample size", "primary endpoint", "power calculation",
        "interim analysis", "subgroup analysis", "p-value", "confidence interval",
        "randomisation", "randomization", "stratification", "biostatistic",
    ],
    "quality_impd": [
        "impd", "drug product", "manufacturing", "batch", "stability",
        "shelf-life", "expiry", "certificate", "gmp", "quality",
        "release", "specification", "analytical", "formulation",
    ],
    "clinical_protocol": [
        "protocol", "section b", "study design", "inclusion criteria",
        "exclusion criteria", "primary objective", "secondary objective",
        "amendment", "clinical study report", "visit schedule",
    ],
    "safety_pharmacovigilance": [
        "pharmacovigilance", "safety", "adverse event", "pv plan",
        "susar", "dsur", "investigator brochure", "reference safety",
        "risk management", "periodic safety",
    ],
    "regulatory_admin": [
        "informed consent", "icf", "consent form", "gdpr", "data protection",
        "fee", "payment", "administrative", "application form", "cover letter",
        "regulatory", "ctis", "submission",
    ],
}


def _extract_features(rfi: Dict[str, Any]) -> np.ndarray:
    """
    Extract the 12 structural features from an RFI record.
    Mirrors the feature extraction logic in draft_router.py._predict_risk_score.
    """
    # Combine all text from considerations
    all_text = ""
    for c in rfi.get("considerations", []):
        all_text += " " + (c.get("concern_text") or "")
        all_text += " " + (c.get("response_text") or "")
    all_text = all_text.lower()

    # Also include category and therapeutic area
    category = (rfi.get("category") or "").lower()
    ta = (rfi.get("therapeutic_area_name") or "").lower()
    combined = all_text + " " + category + " " + ta

    features = {
        "trial_phase": 3,  # Default assumption
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
            kw in all_text for kw in ["protocol missing", "no protocol", "missing protocol section"]
        ),
        "has_statistics_section": not any(
            kw in all_text for kw in ["statistic", "sample size", "primary endpoint"]
        ),
        "has_impd_quality": not any(
            kw in all_text for kw in ["impd", "quality", "drug product", "manufacturing"]
        ),
        "has_safety_pv_plan": not any(
            kw in all_text for kw in ["pharmacovigilance", "safety", "adverse event", "pv plan"]
        ),
        "has_informed_consent": not any(
            kw in all_text for kw in ["informed consent", "consent form", "icf"]
        ),
        "num_mscs": 5,
        "prior_rfi_count": 1,
    }

    return np.array([float(features[f]) for f in FEATURE_NAMES])


def _extract_labels(rfi: Dict[str, Any]) -> np.ndarray:
    """
    Extract ground-truth labels: which RFI categories were triggered by this RFI.
    Uses keyword matching on concern_text to determine which categories apply.
    """
    # Combine all concern texts
    all_concerns = ""
    for c in rfi.get("considerations", []):
        all_concerns += " " + (c.get("concern_text") or "")
    all_concerns = all_concerns.lower()

    labels = []
    for cat in RFI_CATEGORIES:
        keywords = CATEGORY_KEYWORDS[cat]
        triggered = any(kw in all_concerns for kw in keywords)
        labels.append(int(triggered))

    return np.array(labels)


def _generate_synthetic_supplement(n_samples: int = 1500, seed: int = 42):
    """
    Generate synthetic calibration data (same as risk_engine._generate_synthetic_dataset)
    to supplement small real datasets and prevent overfitting.
    """
    rng = np.random.default_rng(seed)
    n = n_samples

    trial_phase = rng.choice([1, 2, 3, 4], size=n, p=[0.25, 0.30, 0.38, 0.07])
    ta_onco = rng.random(n) < 0.35
    ta_rare = rng.random(n) < 0.18
    pc_bio = rng.random(n) < 0.28
    pc_atmp = rng.random(n) < 0.07
    has_sec_b = rng.random(n) > 0.12
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

    def _sigmoid(z):
        return 1 / (1 + np.exp(-z))

    z_stats = 0.9 * (trial_phase >= 3) - 1.8 * has_stats + 0.5 * ta_onco + 0.3 * prior_rfis - 0.5
    y_stats = (rng.random(n) < _sigmoid(z_stats)).astype(int)

    z_qual = 1.2 * (pc_bio | pc_atmp) - 2.0 * has_impd + 0.4 * prior_rfis - 0.3
    y_qual = (rng.random(n) < _sigmoid(z_qual)).astype(int)

    z_clin = -2.2 * has_sec_b + 0.6 * (trial_phase >= 2) + 0.3 * ta_rare + 0.2 * prior_rfis + 0.4
    y_clin = (rng.random(n) < _sigmoid(z_clin)).astype(int)

    z_safe = -2.0 * has_pv + 0.8 * ta_rare + 0.5 * pc_atmp + 0.3 * prior_rfis - 0.1
    y_safe = (rng.random(n) < _sigmoid(z_safe)).astype(int)

    z_admin = 0.04 * num_mscs - 1.5 * has_icf + 0.2 * prior_rfis - 0.8
    y_admin = (rng.random(n) < _sigmoid(z_admin)).astype(int)

    Y = np.column_stack([y_stats, y_qual, y_clin, y_safe, y_admin]).astype(int)
    return X, Y


def fetch_rfis() -> List[Dict[str, Any]]:
    """Fetch all RFIs from Layer 2."""
    logger.info("Fetching RFIs from Layer 2 (%s/rfi)...", LAYER2_URL)
    try:
        resp = httpx.get(f"{LAYER2_URL}/rfi", timeout=30.0)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("Fetched %d RFIs from Layer 2", len(data))
            return data
    except Exception as exc:
        logger.error("Failed to fetch RFIs from Layer 2: %s", exc)
    return []


def retrain(min_real_samples: int = 5) -> Dict[str, Any]:
    """
    Main retraining pipeline.

    1. Fetches resolved RFIs from Layer 2.
    2. Extracts features and labels from real data.
    3. Supplements with synthetic data (weighted lower).
    4. Trains the model and saves to disk.
    """
    all_rfis = fetch_rfis()

    # Filter for completed RFIs with response text
    completed = [
        rfi for rfi in all_rfis
        if rfi.get("status") in ("submitted", "approved")
        and any(c.get("response_text") for c in rfi.get("considerations", []))
    ]
    logger.info("Found %d completed RFIs with responses (out of %d total)", len(completed), len(all_rfis))

    # Extract features and labels from real data
    real_X_list = []
    real_Y_list = []
    for rfi in completed:
        real_X_list.append(_extract_features(rfi))
        real_Y_list.append(_extract_labels(rfi))

    n_real = len(real_X_list)

    # Always supplement with synthetic data for robustness
    # Use more synthetic data when real data is scarce, less when plentiful
    if n_real < min_real_samples:
        n_synthetic = 2000
        logger.info(
            "Only %d real samples (below minimum %d). Using %d synthetic samples as primary training data.",
            n_real, min_real_samples, n_synthetic,
        )
    else:
        # Reduce synthetic proportion as real data grows
        n_synthetic = max(500, 2000 - (n_real * 50))
        logger.info(
            "Using %d real samples + %d synthetic supplement for training.",
            n_real, n_synthetic,
        )

    syn_X, syn_Y = _generate_synthetic_supplement(n_samples=n_synthetic)

    if n_real > 0:
        real_X = np.stack(real_X_list)
        real_Y = np.stack(real_Y_list)

        # Weight real data more heavily by repeating it
        real_weight = max(1, 3 if n_real < 20 else 2)
        X = np.vstack([np.tile(real_X, (real_weight, 1)), syn_X])
        Y = np.vstack([np.tile(real_Y, (real_weight, 1)), syn_Y])
        logger.info(
            "Training dataset: %d rows (%d real × %d + %d synthetic)",
            len(X), n_real, real_weight, n_synthetic,
        )
    else:
        X = syn_X
        Y = syn_Y
        logger.info("No real data available. Training on %d synthetic samples only.", n_synthetic)

    # Train the model
    logger.info("Training GradientBoostingClassifier (MultiOutput)...")
    base_gbc = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        min_samples_leaf=10,
        random_state=42,
    )
    model = MultiOutputClassifier(base_gbc, n_jobs=-1)
    model.fit(X, Y)

    # Build SHAP explainers
    logger.info("Building SHAP TreeExplainers...")
    explainers = [shap.TreeExplainer(est) for est in model.estimators_]

    # Save to disk
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(explainers, EXPLAINER_PATH)
    logger.info("Model saved to %s", MODEL_PATH)
    logger.info("Explainers saved to %s", EXPLAINER_PATH)

    summary = {
        "status": "retrained",
        "total_rfis_fetched": len(all_rfis),
        "completed_rfis_used": n_real,
        "synthetic_supplement": n_synthetic,
        "total_training_rows": len(X),
        "categories": RFI_CATEGORIES,
        "features": FEATURE_NAMES,
        "model_path": str(MODEL_PATH),
    }
    logger.info("Retraining complete: %s", json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    result = retrain()
    print("\n" + "=" * 60)
    print("RETRAINING COMPLETE")
    print("=" * 60)
    print(json.dumps(result, indent=2))
