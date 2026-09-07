import React, { useState, useEffect } from 'react';
import { predictDossierRisk } from '../services/api';

const S = {
  page: { padding: '24px 0', display: 'flex', flexDirection: 'column', gap: 20 },
  headerBox: { display: 'flex', flexDirection: 'column', gap: 4 },
  heading: { fontSize: 18, fontWeight: 700, color: '#fff', letterSpacing: '-0.01em' },
  sub: { fontSize: 13, color: '#777' },

  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 },

  card: {
    background: '#111',
    border: '1px solid #1e1e1e',
    borderRadius: 10,
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  cardTitle: { fontSize: 14, fontWeight: 600, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  cardSub: { fontSize: 11, color: '#666', marginTop: 2 },

  sectionTitle: { fontSize: 11, fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 },

  formGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  fieldGroup: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: 12, color: '#aaa', fontWeight: 500 },

  phaseBtnGroup: { display: 'flex', gap: 6 },
  phaseBtn: (active) => ({
    flex: 1,
    padding: '8px 0',
    background: active ? '#fff' : '#181818',
    color: active ? '#000' : '#888',
    border: active ? '1px solid #fff' : '1px solid #262626',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    textAlign: 'center',
    transition: 'all 0.15s',
  }),

  input: {
    background: '#181818',
    border: '1px solid #262626',
    borderRadius: 6,
    padding: '8px 12px',
    color: '#fff',
    fontSize: 12,
    outline: 'none',
  },

  checkboxRow: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none' },
  checkbox: { width: 15, height: 15, accentColor: '#3b82f6', cursor: 'pointer' },
  checkboxLabel: { fontSize: 12, color: '#ccc' },

  btn: {
    padding: '11px 20px',
    background: '#fff',
    color: '#000',
    border: 'none',
    borderRadius: 6,
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
    transition: 'opacity 0.15s',
    marginTop: 8,
  },

  // Results styling
  categoryCard: (isSelected, riskLevel) => ({
    background: isSelected ? '#161616' : '#0a0a0a',
    border: isSelected ? '1px solid #38bdf8' : '1px solid #1a1a1a',
    borderRadius: 8,
    padding: '12px 14px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    transition: 'all 0.15s',
  }),
  categoryHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  categoryName: { fontSize: 12, fontWeight: 600, color: '#eee', textTransform: 'capitalize' },
  
  badge: (score) => {
    let bg = 'rgba(34, 197, 94, 0.12)';
    let color = '#4ade80';
    let border = 'rgba(34, 197, 94, 0.25)';
    if (score >= 0.6) {
      bg = 'rgba(239, 68, 68, 0.12)';
      color = '#f87171';
      border = 'rgba(239, 68, 68, 0.25)';
    } else if (score >= 0.3) {
      bg = 'rgba(245, 158, 11, 0.12)';
      color = '#fbbf24';
      border = 'rgba(245, 158, 11, 0.25)';
    }
    return {
      fontSize: 11,
      fontWeight: 600,
      fontFamily: '"JetBrains Mono", monospace',
      padding: '2px 8px',
      borderRadius: 4,
      background: bg,
      color: color,
      border: `1px solid ${border}`,
    };
  },

  progressBarBg: { height: 4, background: '#1a1a1a', borderRadius: 2, overflow: 'hidden' },
  progressBarFill: (score) => ({
    height: '100%',
    width: `${Math.round(score * 100)}%`,
    background: score >= 0.6 ? '#f87171' : score >= 0.3 ? '#fbbf24' : '#4ade80',
    transition: 'width 0.3s ease',
  }),

  shapBox: {
    background: '#0a0a0a',
    border: '1px solid #1f1f1f',
    borderRadius: 8,
    padding: 14,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  shapHead: { fontSize: 12, fontWeight: 600, color: '#38bdf8', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  shapRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, padding: '4px 0', borderBottom: '1px dashed #181818' },
  shapFeatureName: { color: '#bbb', fontFamily: '"JetBrains Mono", monospace' },
  shapWeight: (val) => ({
    fontFamily: '"JetBrains Mono", monospace',
    fontWeight: 600,
    color: val > 0 ? '#f87171' : val < 0 ? '#4ade80' : '#777',
  }),

  disclaimerBox: {
    background: 'rgba(245, 158, 11, 0.05)',
    border: '1px solid rgba(245, 158, 11, 0.15)',
    borderRadius: 6,
    padding: '10px 12px',
    fontSize: 11,
    color: '#fbbf24',
    lineHeight: 1.5,
  },
};

const CATEGORY_LABELS = {
  statistics: 'Biostatistics & Endpoints',
  quality_impd: 'IMPD Quality Completeness',
  clinical_protocol: 'Clinical Protocol Design',
  safety_pharmacovigilance: 'Safety & PV Plan',
  regulatory_admin: 'Regulatory & Admin Format',
};

const DEFAULT_FEATURES = {
  trial_phase: 3,
  therapeutic_area_oncology: true,
  therapeutic_area_rare_disease: false,
  product_class_biologic: true,
  product_class_atmp: false,
  has_section_b_protocol: true,
  has_statistics_section: false, // Default: missing stats section triggers high statistics risk
  has_impd_quality: true,
  has_safety_pv_plan: true,
  has_informed_consent: true,
  num_mscs: 8,
  prior_rfi_count: 2,
};

export default function RiskPredictorView() {
  const [features, setFeatures] = useState(DEFAULT_FEATURES);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('statistics');

  const runPrediction = async (customFeatures = features) => {
    setLoading(true);
    try {
      const data = await predictDossierRisk(customFeatures);
      setResult(data);
    } catch (err) {
      console.error('Risk prediction failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runPrediction();
  }, []);

  const handleToggle = (key) => {
    const updated = { ...features, [key]: !features[key] };
    setFeatures(updated);
  };

  const handleNumChange = (key, val) => {
    const num = Math.max(0, parseInt(val, 10) || 0);
    setFeatures({ ...features, [key]: num });
  };

  const predictions = result?.predictions || {};
  const explanationDetail = result?.explanation_detail || {};
  const currentShap = explanationDetail[selectedCategory] || {};

  // Sort features by absolute SHAP impact for the selected category
  const sortedShap = Object.entries(currentShap)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

  return (
    <div style={S.page}>
      {/* Top Header */}
      <div style={S.headerBox}>
        <div style={S.heading}>Layer 4 — Pre-Submission Dossier RFI Risk Engine</div>
        <div style={S.sub}>ML Risk Classifier + Mandatory SHAP Feature Attribution (Clarion Bible §5 & §9)</div>
      </div>

      <div style={S.grid}>
        {/* Left Column: Dossier Input Form */}
        <div style={S.card}>
          <div>
            <div style={S.cardTitle}>
              <span> Draft CTA Dossier Configuration</span>
              <span style={{ fontSize: 11, color: '#666', fontFamily: '"JetBrains Mono", monospace' }}>12 Structural Parameters</span>
            </div>
            <div style={S.cardSub}>Deterministic structural metadata — zero LLM evaluation</div>
          </div>

          {/* Trial Phase */}
          <div style={S.fieldGroup}>
            <label style={S.label}>EU CTR Trial Phase</label>
            <div style={S.phaseBtnGroup}>
              {[1, 2, 3, 4].map((p) => (
                <button
                  key={p}
                  style={S.phaseBtn(features.trial_phase === p)}
                  onClick={() => setFeatures({ ...features, trial_phase: p })}
                >
                  Phase {p}
                </button>
              ))}
            </div>
          </div>

          {/* Numerical Inputs */}
          <div style={S.formGrid}>
            <div style={S.fieldGroup}>
              <label style={S.label}>Member States Concerned (1–30)</label>
              <input
                type="number"
                min="1"
                max="30"
                style={S.input}
                value={features.num_mscs}
                onChange={(e) => handleNumChange('num_mscs', e.target.value)}
              />
            </div>
            <div style={S.fieldGroup}>
              <label style={S.label}>Historical Sponsor RFI Count</label>
              <input
                type="number"
                min="0"
                style={S.input}
                value={features.prior_rfi_count}
                onChange={(e) => handleNumChange('prior_rfi_count', e.target.value)}
              />
            </div>
          </div>

          {/* Therapeutic Areas & Product Classes */}
          <div>
            <div style={S.sectionTitle}>Therapeutic Area & IMP Class</div>
            <div style={S.formGrid}>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.therapeutic_area_oncology}
                  onChange={() => handleToggle('therapeutic_area_oncology')}
                />
                <span style={S.checkboxLabel}>Oncology Target</span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.therapeutic_area_rare_disease}
                  onChange={() => handleToggle('therapeutic_area_rare_disease')}
                />
                <span style={S.checkboxLabel}>Orphan / Rare Disease</span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.product_class_biologic}
                  onChange={() => handleToggle('product_class_biologic')}
                />
                <span style={S.checkboxLabel}>Biologic (Large Molecule)</span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.product_class_atmp}
                  onChange={() => handleToggle('product_class_atmp')}
                />
                <span style={S.checkboxLabel}>ATMP Advanced Therapy</span>
              </label>
            </div>
          </div>

          {/* Dossier Section Completeness */}
          <div>
            <div style={S.sectionTitle}>Required Dossier Sections Present</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.has_section_b_protocol}
                  onChange={() => handleToggle('has_section_b_protocol')}
                />
                <span style={S.checkboxLabel}>Protocol Section B (Objectives & Design)</span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.has_statistics_section}
                  onChange={() => handleToggle('has_statistics_section')}
                />
                <span style={{ ...S.checkboxLabel, color: !features.has_statistics_section ? '#f87171' : '#ccc' }}>
                  Statistics & Sample Size Justification {!features.has_statistics_section && '(Missing - High Risk!)'}
                </span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.has_impd_quality}
                  onChange={() => handleToggle('has_impd_quality')}
                />
                <span style={S.checkboxLabel}>IMPD Quality Documentation</span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.has_safety_pv_plan}
                  onChange={() => handleToggle('has_safety_pv_plan')}
                />
                <span style={S.checkboxLabel}>Safety & Pharmacovigilance Plan</span>
              </label>
              <label style={S.checkboxRow}>
                <input
                  type="checkbox"
                  style={S.checkbox}
                  checked={features.has_informed_consent}
                  onChange={() => handleToggle('has_informed_consent')}
                />
                <span style={S.checkboxLabel}>Informed Consent Form (ICF)</span>
              </label>
            </div>
          </div>

          <button
            style={{ ...S.btn, opacity: loading ? 0.6 : 1 }}
            onClick={() => runPrediction()}
            disabled={loading}
          >
            {loading ? 'Evaluating Risk Model…' : 'Evaluate Dossier Risk & SHAP Attributions'}
          </button>
        </div>

        {/* Right Column: RFI Category Risk Scores & SHAP Breakdown */}
        <div style={S.card}>
          <div>
            <div style={S.cardTitle}>
              <span> Predicted RFI Category Likelihoods</span>
              <span style={{ fontSize: 11, color: '#4ade80', fontFamily: '"JetBrains Mono", monospace' }}>SHAP Verified</span>
            </div>
            <div style={S.cardSub}>Click any category to inspect feature drivers</div>
          </div>

          {/* RFI Categories */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Object.entries(predictions).map(([catKey, prob]) => {
              const label = CATEGORY_LABELS[catKey] || catKey;
              const pct = Math.round(prob * 100);
              const isSelected = selectedCategory === catKey;

              return (
                <div
                  key={catKey}
                  style={S.categoryCard(isSelected, prob)}
                  onClick={() => setSelectedCategory(catKey)}
                >
                  <div style={S.categoryHead}>
                    <span style={S.categoryName}>{label}</span>
                    <span style={S.badge(prob)}>{pct}% Likelihood</span>
                  </div>
                  <div style={S.progressBarBg}>
                    <div style={S.progressBarFill(prob)} />
                  </div>
                </div>
              );
            })}
          </div>

          {/* SHAP Feature Attribution Detail Panel */}
          {selectedCategory && (
            <div style={S.shapBox}>
              <div style={S.shapHead}>
                <span> SHAP Feature Drivers — {CATEGORY_LABELS[selectedCategory]}</span>
                <span style={{ fontSize: 10, color: '#888' }}>TreeExplainer</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {sortedShap.map(([feat, val]) => (
                  <div key={feat} style={S.shapRow}>
                    <span style={S.shapFeatureName}>{feat}</span>
                    <span style={S.shapWeight(val)}>
                      {val > 0 ? `+${val.toFixed(4)}` : val.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Mandatory Regulatory Disclaimer */}
          <div style={S.disclaimerBox}>
            <strong>️ Mandatory Regulatory Guardrail (§5 Decision Table):</strong><br />
            {result?.disclaimer ||
              'These are probabilistic likelihood estimates derived from an ML classifier (GradientBoostingClassifier + SHAP). They suggest risk — they do NOT make binding regulatory decisions.'}
          </div>
        </div>
      </div>
    </div>
  );
}
