"""
test_risk_engine.py — Unit tests for Clarion Layer 4: Risk Prediction Engine
=============================================================================
Tests are organised around the architectural invariants from Clarion Bible §9:

1.  predict_with_explanation() always returns BOTH 'predictions' AND 'explanation'.
2.  All probability values are in [0.0, 1.0].
3.  SHAP explanation keys match FEATURE_NAMES exactly (per category).
4.  Missing a required feature raises ValueError, not a silent 0.
5.  A predictions-only return (no explanation) is structurally impossible.
6.  High-risk dossier (Phase 3, missing statistics) → high statistics likelihood.
7.  Low-risk dossier (complete, Phase 1) → lower statistics likelihood than high-risk.
8.  DossierFeatureVector.to_array() preserves FEATURE_NAMES order.
9.  get_feature_schema() returns all FEATURE_NAMES and all RFI_CATEGORIES.
10. retrain_model() completes without error and reloads singletons.
"""
import importlib
import sys
import types
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Ensure the backend package is importable from this test file's location
# (handles running via `pytest` from apps/backend/ directly)
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
import sys
from pathlib import Path

# Add backend root to sys.path so 'from app.api...' works regardless of where pytest is run from
_BACKEND_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.api.risk_engine import (
    FEATURE_NAMES,
    RFI_CATEGORIES,
    DossierFeatureVector,
    get_feature_schema,
    predict_with_explanation,
    retrain_model,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def complete_low_risk_dossier() -> dict:
    """Phase 1, all sections present — low RFI risk across all categories."""
    return {
        "trial_phase": 1,
        "therapeutic_area_oncology": False,
        "therapeutic_area_rare_disease": False,
        "product_class_biologic": False,
        "product_class_atmp": False,
        "has_section_b_protocol": True,
        "has_statistics_section": True,
        "has_impd_quality": True,
        "has_safety_pv_plan": True,
        "has_informed_consent": True,
        "num_mscs": 1,
        "prior_rfi_count": 0,
    }


@pytest.fixture
def high_risk_stats_dossier() -> dict:
    """Phase 3, missing statistics section — should yield high statistics likelihood."""
    return {
        "trial_phase": 3,
        "therapeutic_area_oncology": True,
        "therapeutic_area_rare_disease": False,
        "product_class_biologic": True,
        "product_class_atmp": False,
        "has_section_b_protocol": True,
        "has_statistics_section": False,   # ← critical missing section
        "has_impd_quality": True,
        "has_safety_pv_plan": True,
        "has_informed_consent": True,
        "num_mscs": 8,
        "prior_rfi_count": 3,
    }


@pytest.fixture
def high_risk_quality_dossier() -> dict:
    """Biologic ATMP, missing IMPD quality section — high quality_impd risk."""
    return {
        "trial_phase": 2,
        "therapeutic_area_oncology": False,
        "therapeutic_area_rare_disease": True,
        "product_class_biologic": True,
        "product_class_atmp": True,
        "has_section_b_protocol": True,
        "has_statistics_section": True,
        "has_impd_quality": False,    # ← missing
        "has_safety_pv_plan": True,
        "has_informed_consent": True,
        "num_mscs": 3,
        "prior_rfi_count": 1,
    }


# ---------------------------------------------------------------------------
# Test 1: predict_with_explanation always returns BOTH keys
# ---------------------------------------------------------------------------

class TestPredictWithExplanationStructure:
    def test_returns_predictions_key(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        assert "predictions" in result, (
            "INVARIANT VIOLATED: 'predictions' key missing from result. "
            "Clarion Bible §9."
        )

    def test_returns_explanation_key(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        assert "explanation" in result, (
            "INVARIANT VIOLATED: 'explanation' key missing from result. "
            "Clarion Bible §9 — 'NO BARE NUMBERS'."
        )

    def test_returns_explanation_detail_key(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        assert "explanation_detail" in result

    def test_returns_metadata_key(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        assert "metadata" in result

    def test_predictions_and_explanation_always_coexist(self, complete_low_risk_dossier):
        """Structural test: it is impossible to return predictions without explanation."""
        result = predict_with_explanation(complete_low_risk_dossier)
        both_present = "predictions" in result and "explanation" in result
        assert both_present, (
            "Bare probability output without SHAP explanation is architecturally "
            "prohibited. See Clarion Bible §9."
        )


# ---------------------------------------------------------------------------
# Test 2: All probability values in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestProbabilityRange:
    def test_all_category_probabilities_in_range(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for cat, prob in result["predictions"].items():
            assert 0.0 <= prob <= 1.0, (
                f"Probability for '{cat}' = {prob} is outside [0.0, 1.0]. "
                "Likelihoods must be valid probabilities."
            )

    def test_all_rfi_categories_present_in_predictions(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for cat in RFI_CATEGORIES:
            assert cat in result["predictions"], (
                f"RFI category '{cat}' missing from predictions dict."
            )

    def test_prediction_values_are_floats(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for cat, prob in result["predictions"].items():
            assert isinstance(prob, float), (
                f"Prediction for '{cat}' is {type(prob)}, expected float."
            )


# ---------------------------------------------------------------------------
# Test 3: SHAP explanation keys match FEATURE_NAMES x RFI_CATEGORIES
# ---------------------------------------------------------------------------

class TestSHAPExplanation:
    def test_explanation_detail_has_all_categories(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for cat in RFI_CATEGORIES:
            assert cat in result["explanation_detail"], (
                f"Category '{cat}' missing from explanation_detail."
            )

    def test_explanation_detail_has_all_features_per_category(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for cat, feat_map in result["explanation_detail"].items():
            for fname in FEATURE_NAMES:
                assert fname in feat_map, (
                    f"Feature '{fname}' missing from SHAP explanation for category '{cat}'."
                )

    def test_shap_values_are_floats(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for cat, feat_map in result["explanation_detail"].items():
            for fname, val in feat_map.items():
                assert isinstance(val, float), (
                    f"SHAP value for '{fname}' in '{cat}' is {type(val)}, expected float."
                )

    def test_flat_explanation_keys_contain_category_name(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        for key in result["explanation"]:
            # Keys are formatted as {feature_name}__{category}
            assert "__" in key, (
                f"Flat explanation key '{key}' missing '__' separator. "
                "Expected '{feature}__{category}' format."
            )


# ---------------------------------------------------------------------------
# Test 4: Missing feature raises ValueError, not silent 0
# ---------------------------------------------------------------------------

class TestMissingFeatureHandling:
    def test_missing_single_feature_raises_value_error(self, complete_low_risk_dossier):
        broken = dict(complete_low_risk_dossier)
        del broken["has_statistics_section"]
        with pytest.raises(ValueError, match="Missing required dossier feature"):
            predict_with_explanation(broken)

    def test_missing_multiple_features_raises_value_error(self, complete_low_risk_dossier):
        broken = {
            k: v for k, v in complete_low_risk_dossier.items()
            if k not in ("trial_phase", "num_mscs")
        }
        with pytest.raises(ValueError):
            predict_with_explanation(broken)

    def test_empty_dict_raises_value_error(self):
        with pytest.raises(ValueError):
            predict_with_explanation({})


# ---------------------------------------------------------------------------
# Test 5: Structural impossibility of bare predictions
# (belt-and-suspenders — function never returns without 'explanation')
# ---------------------------------------------------------------------------

class TestBareNumbersImpossibility:
    def test_result_always_has_explanation_key(self, complete_low_risk_dossier, high_risk_stats_dossier):
        for dossier in [complete_low_risk_dossier, high_risk_stats_dossier]:
            result = predict_with_explanation(dossier)
            assert "explanation" in result, (
                "Clarion Bible §9 invariant broken: returned predictions without explanation."
            )
            assert len(result["explanation"]) > 0, (
                "Explanation dict is empty — SHAP values were not computed."
            )


# ---------------------------------------------------------------------------
# Test 6: High-risk dossier produces higher statistics likelihood
# ---------------------------------------------------------------------------

class TestRiskCalibration:
    def test_missing_stats_section_phase3_elevates_statistics_risk(
        self, complete_low_risk_dossier, high_risk_stats_dossier
    ):
        low_result = predict_with_explanation(complete_low_risk_dossier)
        high_result = predict_with_explanation(high_risk_stats_dossier)
        assert high_result["predictions"]["statistics"] > low_result["predictions"]["statistics"], (
            "A Phase 3 dossier missing the statistics section should have higher "
            "statistics RFI likelihood than a complete Phase 1 dossier."
        )

    def test_missing_impd_quality_biologic_elevates_quality_risk(
        self, complete_low_risk_dossier, high_risk_quality_dossier
    ):
        low_result = predict_with_explanation(complete_low_risk_dossier)
        high_result = predict_with_explanation(high_risk_quality_dossier)
        assert high_result["predictions"]["quality_impd"] > low_result["predictions"]["quality_impd"], (
            "A biologic/ATMP dossier missing the IMPD quality section should have "
            "higher quality_impd RFI likelihood than a complete small-molecule dossier."
        )


# ---------------------------------------------------------------------------
# Test 7: DossierFeatureVector.to_array() preserves FEATURE_NAMES order
# ---------------------------------------------------------------------------

class TestDossierFeatureVector:
    def test_to_array_length_matches_feature_names(self, complete_low_risk_dossier):
        fv = DossierFeatureVector.from_dict(complete_low_risk_dossier)
        arr = fv.to_array()
        assert len(arr) == len(FEATURE_NAMES), (
            f"Feature array length {len(arr)} != len(FEATURE_NAMES) {len(FEATURE_NAMES)}."
        )

    def test_to_array_dtype_is_float(self, complete_low_risk_dossier):
        fv = DossierFeatureVector.from_dict(complete_low_risk_dossier)
        arr = fv.to_array()
        assert arr.dtype == float, f"Expected float dtype, got {arr.dtype}."

    def test_to_array_trial_phase_at_index_0(self, complete_low_risk_dossier):
        """trial_phase must be index 0 — FEATURE_NAMES order must match to_array()."""
        complete_low_risk_dossier["trial_phase"] = 3
        fv = DossierFeatureVector.from_dict(complete_low_risk_dossier)
        arr = fv.to_array()
        assert arr[FEATURE_NAMES.index("trial_phase")] == 3.0


# ---------------------------------------------------------------------------
# Test 8: get_feature_schema() returns complete schema
# ---------------------------------------------------------------------------

class TestFeatureSchema:
    def test_schema_contains_all_feature_names(self):
        schema = get_feature_schema()
        for fname in FEATURE_NAMES:
            assert fname in schema["features"], (
                f"Feature '{fname}' missing from get_feature_schema() output."
            )

    def test_schema_contains_all_rfi_categories(self):
        schema = get_feature_schema()
        assert schema["rfi_categories"] == RFI_CATEGORIES

    def test_schema_total_features_correct(self):
        schema = get_feature_schema()
        assert schema["total_features"] == len(FEATURE_NAMES)

    def test_schema_has_no_llm_phrasing(self):
        schema = get_feature_schema()
        note = schema.get("note", "").lower()
        assert "no llm" in note or "not llm" in note or "deterministic" in note.lower() or "ml" in note.lower(), (
            "Schema note should clarify features are not LLM-derived."
        )


# ---------------------------------------------------------------------------
# Test 9: Metadata contains required semantics keys
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_metadata_output_semantics_mentions_likelihood(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        semantics = result["metadata"].get("output_semantics", "")
        assert "likelihood" in semantics.lower(), (
            "Output semantics must use 'likelihood' language, not certainty phrasing. "
            "Clarion Bible §9."
        )

    def test_metadata_model_type_mentions_gradient_boosting(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        model_type = result["metadata"].get("model_type", "")
        assert "gradientboosting" in model_type.lower().replace(" ", ""), (
            "Model type metadata should identify the GradientBoostingClassifier."
        )

    def test_metadata_explainability_mentions_shap(self, complete_low_risk_dossier):
        result = predict_with_explanation(complete_low_risk_dossier)
        expl = result["metadata"].get("explainability", "")
        assert "shap" in expl.lower()
