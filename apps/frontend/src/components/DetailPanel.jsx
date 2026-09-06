import React, { useState, useEffect, useCallback } from 'react';
import { advanceRfiStage, predictDossierRisk, searchSemantic } from '../services/api';

const STAGE_ORDER = ['received', 'ready_for_response', 'awaiting_response', 'drafting', 'pending_approval', 'approved', 'submitted'];
const STAGE_LABELS = {
  received: 'Received',
  ready_for_response: 'Ready for Response',
  awaiting_response: 'Awaiting Response',
  drafting: 'Drafting',
  pending_approval: 'Pending Approval',
  approved: 'Approved',
  submitted: 'Submitted',
};

const RISK_LABELS = {
  statistics: 'Biostatistics',
  quality_impd: 'Quality / IMPD',
  clinical_protocol: 'Clinical Protocol',
  safety_pharmacovigilance: 'Safety & PV',
  regulatory_admin: 'Regulatory Admin',
};

function getSlaInfo(sla_due_at) {
  if (!sla_due_at) return { label: 'No SLA set', color: 'var(--text-dim)', bg: 'var(--bg)', pct: 0 };
  const now = Date.now();
  const due = new Date(sla_due_at).getTime();
  const totalMs = 72 * 60 * 60 * 1000;
  const diffMs = due - now;
  if (diffMs <= 0) return { label: 'OVERDUE', color: 'var(--red)', bg: 'var(--red-light)', pct: 0 };
  const hours = Math.floor(diffMs / 3600000);
  const mins = Math.floor((diffMs % 3600000) / 60000);
  const pct = Math.min(100, Math.round((diffMs / totalMs) * 100));
  const label = hours > 24
    ? `${Math.floor(hours / 24)} days, ${hours % 24}h remaining`
    : `${hours}h ${mins}m remaining`;
  if (pct > 50) return { label, color: 'var(--green)', bg: 'var(--green-light)', pct };
  if (pct > 20) return { label, color: 'var(--amber)', bg: 'var(--amber-light)', pct };
  return { label, color: 'var(--red)', bg: 'var(--red-light)', pct };
}

// Build a proper DossierFeaturesRequest from the RFI data
function buildRiskFeatures(rfi) {
  const category = (rfi.category || '').toLowerCase();
  const area = (rfi.therapeutic_area_name || '').toLowerCase();
  return {
    trial_phase: 2, // default; not in RFI data
    therapeutic_area_oncology: area.includes('oncol') || area.includes('cancer') || area.includes('tumor'),
    therapeutic_area_rare_disease: area.includes('rare') || area.includes('orphan'),
    product_class_biologic: area.includes('biolog') || area.includes('monoclonal'),
    product_class_atmp: area.includes('gene') || area.includes('cell therapy') || area.includes('atmp'),
    has_section_b_protocol: !category.includes('protocol'),
    has_statistics_section: !category.includes('statistic'),
    has_impd_quality: !category.includes('impd') && !category.includes('quality'),
    has_safety_pv_plan: !category.includes('safety') && !category.includes('pharmacovig'),
    has_informed_consent: !category.includes('consent'),
    num_mscs: 1,
    prior_rfi_count: 0,
  };
}

const s = {
  overlay: {
    position: 'fixed',
    top: 0, right: 0, bottom: 0, left: 0,
    background: 'rgba(26,29,46,0.35)',
    backdropFilter: 'blur(3px)',
    zIndex: 100,
    display: 'flex',
    justifyContent: 'flex-end',
  },
  panel: {
    width: 580,
    maxWidth: '100vw',
    background: 'var(--bg-sidebar)',
    borderLeft: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
    animation: 'slideInRight 0.22s ease',
    boxShadow: '-8px 0 48px rgba(0,0,0,0.12)',
  },
  header: {
    padding: '24px 30px',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
    position: 'sticky',
    top: 0,
    background: 'var(--bg-sidebar)',
    zIndex: 1,
  },
  rfiId: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 13,
    fontWeight: 700,
    color: 'var(--text)',
    marginBottom: 4,
  },
  subtitle: { fontSize: 14, color: 'var(--text-muted)' },
  closeBtn: {
    background: 'transparent',
    border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '7px 14px',
    fontSize: 13,
    flexShrink: 0,
    transition: 'all 0.15s',
  },
  body: {
    padding: '24px 30px',
    display: 'flex',
    flexDirection: 'column',
    gap: 26,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.10em',
    color: 'var(--text-dim)',
    marginBottom: 10,
  },
  slaCard: (color, bg) => ({
    background: bg,
    borderRadius: 'var(--radius-md)',
    padding: '18px 22px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    border: `1px solid ${color}44`,
  }),
  slaBig: (color) => ({
    fontSize: 18,
    fontWeight: 800,
    color,
    fontFamily: "'JetBrains Mono', monospace",
    textAlign: 'right',
  }),
  metaGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
  metaBox: {
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 16px',
  },
  metaLabel: {
    fontSize: 10,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    marginBottom: 4,
  },
  metaValue: { fontSize: 14, color: 'var(--text)', fontWeight: 500 },
  riskCard: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '18px 22px',
    boxShadow: 'var(--shadow-sm)',
  },
  riskRow: { marginBottom: 14 },
  riskRowLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 5,
    fontSize: 13,
  },
  riskBarTrack: {
    height: 8,
    borderRadius: 4,
    background: 'var(--border)',
    overflow: 'hidden',
  },
  riskBarFill: (pct) => {
    const color = pct >= 60 ? 'var(--red)' : pct >= 35 ? 'var(--amber)' : 'var(--green)';
    return {
      height: '100%',
      width: `${pct}%`,
      borderRadius: 4,
      background: color,
      transition: 'width 0.6s ease',
    };
  },
  riskPct: (pct) => ({
    fontSize: 13,
    fontWeight: 700,
    fontFamily: "'JetBrains Mono', monospace",
    color: pct >= 60 ? 'var(--red)' : pct >= 35 ? 'var(--amber)' : 'var(--green)',
  }),
  considerationCard: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '18px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    boxShadow: 'var(--shadow-sm)',
  },
  numBadge: {
    width: 26, height: 26,
    borderRadius: '50%',
    background: 'var(--accent-blue-light)',
    color: 'var(--accent-blue)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 11,
    fontWeight: 700,
    flexShrink: 0,
  },
  textLabel: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    color: 'var(--text-dim)',
    marginBottom: 5,
  },
  textBlock: { fontSize: 14, color: 'var(--text)', lineHeight: 1.65 },
  concernBlock: {
    background: 'var(--accent-pink-light)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 14px',
    fontSize: 14,
    color: 'var(--text)',
    lineHeight: 1.65,
    borderLeft: '3px solid var(--accent-pink)',
  },
  responseBlock: {
    background: 'var(--accent-blue-light)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 14px',
    fontSize: 14,
    color: 'var(--text)',
    lineHeight: 1.65,
    borderLeft: '3px solid var(--accent-blue)',
  },
  recommendCard: {
    background: 'var(--green-light)',
    border: '1px solid rgba(45,184,122,0.2)',
    borderRadius: 'var(--radius-md)',
    padding: '16px 20px',
    fontSize: 14,
    color: 'var(--text)',
    lineHeight: 1.65,
  },
  divider: { height: 1, background: 'var(--border)' },
  stageWrap: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  stagePill: (active, done) => ({
    padding: '7px 14px',
    borderRadius: 20,
    fontSize: 12,
    fontWeight: active ? 700 : 500,
    border: `1.5px solid ${active ? 'var(--accent-blue)' : done ? 'rgba(45,184,122,0.35)' : 'var(--border)'}`,
    background: active ? 'var(--accent-blue)' : done ? 'var(--green-light)' : 'transparent',
    color: active ? '#fff' : done ? 'var(--green)' : 'var(--text-dim)',
  }),
  advanceBtn: {
    marginTop: 12,
    padding: '13px',
    background: 'linear-gradient(135deg, var(--accent-blue) 0%, #6f8fff 100%)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    width: '100%',
    boxShadow: '0 2px 10px rgba(79,114,255,0.25)',
    transition: 'opacity 0.15s',
  },
  statusMsg: (ok) => ({
    fontSize: 13,
    color: ok ? 'var(--green)' : 'var(--red)',
    marginTop: 8,
    padding: '10px 14px',
    background: ok ? 'var(--green-light)' : 'var(--red-light)',
    borderRadius: 'var(--radius-sm)',
  }),
  loadingText: {
    fontSize: 13,
    color: 'var(--text-dim)',
    fontStyle: 'italic',
    padding: '10px 0',
  },
  draftCard: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '18px 22px',
    boxShadow: 'var(--shadow-sm)',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  draftTextarea: {
    width: '100%',
    minHeight: 130,
    background: 'var(--bg)',
    border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 14px',
    color: 'var(--text)',
    fontSize: 14,
    lineHeight: 1.65,
    outline: 'none',
    resize: 'vertical',
    transition: 'border-color 0.15s',
    fontFamily: 'inherit',
  },
  scoreBtn: (loading) => ({
    padding: '11px 20px',
    background: loading ? 'var(--bg)' : 'var(--accent-pink)',
    color: loading ? 'var(--text-dim)' : '#fff',
    border: loading ? '1.5px solid var(--border)' : 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 13,
    fontWeight: 600,
    cursor: loading ? 'not-allowed' : 'pointer',
    alignSelf: 'flex-end',
    transition: 'all 0.15s',
    boxShadow: loading ? 'none' : '0 2px 10px rgba(240,98,146,0.3)',
  }),
  disclaimer: {
    fontSize: 11,
    color: 'var(--text-dim)',
    lineHeight: 1.5,
    padding: '10px 14px',
    background: 'var(--bg)',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
  },
};

function SlaTicker({ sla_due_at }) {
  const [info, setInfo] = useState(() => getSlaInfo(sla_due_at));
  useEffect(() => {
    const t = setInterval(() => setInfo(getSlaInfo(sla_due_at)), 10000);
    return () => clearInterval(t);
  }, [sla_due_at]);

  return (
    <div style={s.slaCard(info.color, info.bg)}>
      <div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Submission deadline</div>
        <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 3 }}>
          {sla_due_at
            ? new Date(sla_due_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
            : '—'}
        </div>
      </div>
      <div style={s.slaBig(info.color)}>{info.label}</div>
    </div>
  );
}

function RiskBars({ predictions }) {
  if (!predictions) return null;
  return (
    <div>
      {Object.entries(RISK_LABELS).map(([key, label]) => {
        const pct = Math.round((predictions[key] ?? 0) * 100);
        return (
          <div key={key} style={s.riskRow}>
            <div style={s.riskRowLabel}>
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{label}</span>
              <span style={s.riskPct(pct)}>{pct}%</span>
            </div>
            <div style={s.riskBarTrack}>
              <div style={s.riskBarFill(pct)} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DraftResponseSection({ rfi, suggestedText }) {
  const [draft, setDraft] = useState('');
  const [draftRisk, setDraftRisk] = useState(null);
  const [scoring, setScoring] = useState(false);

  // Pre-fill draft with AI suggestion when available
  useEffect(() => {
    if (suggestedText && !draft) setDraft(suggestedText);
  }, [suggestedText]);

  const scoreDraft = async () => {
    if (!draft.trim() || scoring) return;
    setScoring(true);
    setDraftRisk(null);
    try {
      // Build features from RFI context + infer from draft text
      const draftLower = draft.toLowerCase();
      const features = {
        ...buildRiskFeatures(rfi),
        // Infer completeness from draft content
        has_statistics_section: draftLower.includes('statistic') || draftLower.includes('analysis') || !rfi.category?.toLowerCase().includes('statistic'),
        has_impd_quality: draftLower.includes('quality') || draftLower.includes('impd') || !rfi.category?.toLowerCase().includes('impd'),
        has_safety_pv_plan: draftLower.includes('safety') || draftLower.includes('pharmacovig') || !rfi.category?.toLowerCase().includes('safety'),
        has_informed_consent: draftLower.includes('consent') || !rfi.category?.toLowerCase().includes('consent'),
        prior_rfi_count: 1, // This IS a prior RFI
      };
      const result = await predictDossierRisk(features);
      setDraftRisk(result);
    } catch (err) {
      console.error('[DraftResponseSection] Risk scoring failed:', err);
    } finally {
      setScoring(false);
    }
  };

  return (
    <div style={s.draftCard}>
      <div>
        <div style={{ ...s.textLabel, color: 'var(--accent-pink)', marginBottom: 6 }}>Draft Response</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
          Write or refine your response to this RFI. The AI suggestion below (from similar past cases) has been pre-filled as a starting point.
        </div>
        <textarea
          id="draft-response-textarea"
          style={s.draftTextarea}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          placeholder="Start typing your response here, or use the AI suggestion above as a starting point..."
          onFocus={e => { e.target.style.borderColor = 'var(--accent-pink)'; }}
          onBlur={e => { e.target.style.borderColor = 'var(--border)'; }}
        />
      </div>

      <button
        id="score-draft-btn"
        style={s.scoreBtn(scoring)}
        disabled={scoring || !draft.trim()}
        onClick={scoreDraft}
      >
        {scoring ? 'Scoring…' : '🔬 Score this Draft'}
      </button>

      {draftRisk && (
        <div>
          <div style={{ ...s.textLabel, marginBottom: 8 }}>Risk Assessment for Your Draft</div>
          <div style={s.riskBarTrack} />
          <RiskBars predictions={draftRisk.predictions} />
          <div style={s.disclaimer}>
            {draftRisk.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DetailPanel({ rfi, onClose, onStageAdvanced }) {
  const [advancing, setAdvancing] = useState(false);
  const [stageMsg, setStageMsg] = useState('');
  const [stageMsgOk, setStageMsgOk] = useState(true);
  const [risk, setRisk] = useState(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [recsLoading, setRecsLoading] = useState(false);

  const currentStage = rfi.workflow_state?.current_stage || rfi.status || 'received';
  const currentIdx = STAGE_ORDER.indexOf(currentStage);

  // Load risk with correct feature schema
  useEffect(() => {
    setRisk(null);
    setRiskLoading(true);
    predictDossierRisk(buildRiskFeatures(rfi))
      .then(res => setRisk(res))
      .catch(err => { console.error('[DetailPanel] Risk prediction failed:', err); setRisk(null); })
      .finally(() => setRiskLoading(false));
  }, [rfi.id]);

  // Load similar past responses
  useEffect(() => {
    const firstConcern = rfi.considerations?.find(c => c.concern_text)?.concern_text;
    if (!firstConcern) { setRecommendations([]); return; }
    setRecsLoading(true);
    searchSemantic(firstConcern, 3)
      .then(res => setRecommendations(res.results?.slice(0, 3) || []))
      .catch(err => { console.error('[DetailPanel] Recommendations fetch failed:', err); setRecommendations([]); })
      .finally(() => setRecsLoading(false));
  }, [rfi.id]);

  const advanceToNext = useCallback(async () => {
    const nextStage = STAGE_ORDER[currentIdx + 1];
    if (!nextStage || advancing) return;
    setAdvancing(true);
    setStageMsg('');
    try {
      await advanceRfiStage(rfi.id, nextStage);
      setStageMsgOk(true);
      setStageMsg(`Advanced to ${STAGE_LABELS[nextStage]}`);
      onStageAdvanced?.();
    } catch (err) {
      console.error('[DetailPanel] Stage advance failed:', err);
      setStageMsgOk(false);
      setStageMsg('Could not advance stage — check Layer 2 is running.');
    } finally {
      setAdvancing(false);
    }
  }, [rfi.id, currentIdx, advancing, onStageAdvanced]);

  // Collect best suggested draft text from recommendations
  const suggestedDraft = recommendations[0]?.rfi?.considerations?.[0]?.response_text || '';

  return (
    <div style={s.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={s.panel}>
        {/* Header */}
        <div style={s.header}>
          <div>
            <div style={s.rfiId}>{rfi.rfi_id}</div>
            <div style={s.subtitle}>{rfi.nca_country} · {rfi.therapeutic_area_name || '—'}</div>
          </div>
          <button
            id="detail-panel-close"
            style={s.closeBtn}
            onClick={onClose}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            ✕ Close
          </button>
        </div>

        <div style={s.body}>

          {/* SLA */}
          <div>
            <div style={s.sectionTitle}>⏱ Time Remaining</div>
            <SlaTicker sla_due_at={rfi.workflow_state?.sla_due_at} />
          </div>

          <div style={s.divider} />

          {/* Details */}
          <div>
            <div style={s.sectionTitle}>📋 Details</div>
            <div style={s.metaGrid}>
              {[['Country', rfi.nca_country], ['Category', rfi.category], ['Submit Date', rfi.submit_date], ['Due Date', rfi.due_date]].map(([label, value]) => (
                <div key={label} style={s.metaBox}>
                  <div style={s.metaLabel}>{label}</div>
                  <div style={s.metaValue}>{value || '—'}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={s.divider} />

          {/* Risk Assessment */}
          <div>
            <div style={s.sectionTitle}>⚠ Risk Assessment (per Category)</div>
            <div style={s.riskCard}>
              {riskLoading ? (
                <div style={s.loadingText}>Calculating risk scores…</div>
              ) : risk?.predictions ? (
                <>
                  <RiskBars predictions={risk.predictions} />
                  <div style={s.disclaimer}>{risk.disclaimer}</div>
                </>
              ) : (
                <div style={s.loadingText}>Risk model unavailable — start the Layer 1 backend.</div>
              )}
            </div>
          </div>

          <div style={s.divider} />

          {/* Considerations */}
          {rfi.considerations?.length > 0 && (
            <div>
              <div style={s.sectionTitle}>📝 Considerations ({rfi.considerations.length})</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {rfi.considerations.map((c, i) => (
                  <div key={c.id || i} style={s.considerationCard}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={s.numBadge}>{c.number || i + 1}</div>
                      {c.ctr_article_name && (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.ctr_article_name}</div>
                      )}
                    </div>

                    {c.concern_text ? (
                      <div>
                        <div style={s.textLabel}>🔴 Concern (NCA Question)</div>
                        <div style={s.concernBlock}>{c.concern_text}</div>
                      </div>
                    ) : null}

                    {c.response_text ? (
                      <div>
                        <div style={s.textLabel}>🔵 Sponsor Response</div>
                        <div style={s.responseBlock}>{c.response_text}</div>
                      </div>
                    ) : null}

                    {c.outcome_status && (
                      <div style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>
                        ✓ Outcome: {c.outcome_status}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Similar Past Responses */}
          <div>
            <div style={s.sectionTitle}>💡 Similar Past Responses</div>
            {recsLoading ? (
              <div style={s.loadingText}>Searching regulatory memory…</div>
            ) : recommendations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {recommendations.map((rec, i) => (
                  <div key={i} style={s.recommendCard}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--green)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
                      Similar Case #{i + 1} · Match {Math.round((rec.score || 0) * 100)}%
                    </div>
                    <div>
                      {rec.rfi?.considerations?.[0]?.response_text || rec.rfi?.rfi_text || 'No response text available.'}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ ...s.loadingText, padding: '12px 16px', background: 'var(--bg)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                {rfi.considerations?.find(c => c.concern_text)
                  ? 'No similar cases found in the database yet.'
                  : 'No concern text available to search for similar cases.'}
              </div>
            )}
          </div>

          {/* Draft Response */}
          <div>
            <div style={s.sectionTitle}>✍ Draft Your Response</div>
            <DraftResponseSection rfi={rfi} suggestedText={suggestedDraft} />
          </div>

          <div style={s.divider} />

          {/* Workflow Stage */}
          <div>
            <div style={s.sectionTitle}>🔄 Workflow Stage</div>
            <div style={s.stageWrap}>
              {STAGE_ORDER.map((stage, idx) => (
                <div key={stage} style={s.stagePill(idx === currentIdx, idx < currentIdx)}>
                  {idx < currentIdx ? '✓ ' : ''}{STAGE_LABELS[stage]}
                </div>
              ))}
            </div>

            {currentIdx < STAGE_ORDER.length - 1 ? (
              <>
                <button
                  id="advance-stage-btn"
                  style={{ ...s.advanceBtn, opacity: advancing ? 0.65 : 1 }}
                  disabled={advancing}
                  onClick={advanceToNext}
                >
                  {advancing ? 'Advancing…' : `Advance → ${STAGE_LABELS[STAGE_ORDER[currentIdx + 1]]}`}
                </button>
                {stageMsg && <div style={s.statusMsg(stageMsgOk)}>{stageMsg}</div>}
              </>
            ) : (
              <div style={{ ...s.statusMsg(true), marginTop: 12 }}>
                ✓ This RFI has been fully submitted.
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
