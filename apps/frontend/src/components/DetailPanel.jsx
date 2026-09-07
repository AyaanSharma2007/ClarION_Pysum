import React, { useState, useEffect, useCallback } from 'react';
import { advanceRfiStage, searchSemantic, searchRecommend, draftAiResponse, getDraftHistory, evaluateManualDraft } from '../services/api';
import MiniProgressBar from './MiniProgressBar';
import SimilarResponsesModal from './SimilarResponsesModal';

const STAGE_ORDER = ['awaiting_response', 'drafting', 'pending_approval', 'approved', 'submitted'];
const STAGE_LABELS = {
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

function getSlaInfo(sla_due_at, rfi_type) {
  if (!sla_due_at) return { label: 'No SLA set', color: 'var(--text-dim)', bg: 'var(--bg)', pct: 0 };
  const now = Date.now();
  const due = new Date(sla_due_at).getTime();
  const days = (rfi_type || '').toLowerCase() === 'assessment' ? 12 : 10;
  const totalMs = days * 24 * 60 * 60 * 1000;
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
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--text)',
    letterSpacing: '0.02em',
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
    const color = pct <= 40 ? 'var(--red)' : pct <= 70 ? 'var(--amber)' : 'var(--green)';
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
    color: pct <= 40 ? 'var(--red)' : pct <= 70 ? 'var(--amber)' : 'var(--green)',
  }),
  acceptanceBarFill: (pct) => {
    const color = pct < 50 ? 'var(--red)' : pct <= 65 ? 'var(--amber)' : 'var(--green)';
    return {
      height: '100%',
      width: `${pct}%`,
      borderRadius: 4,
      background: color,
      transition: 'width 0.6s ease',
    };
  },
  acceptancePct: (pct) => ({
    fontSize: 13,
    fontWeight: 700,
    fontFamily: "'JetBrains Mono', monospace",
    color: pct < 50 ? 'var(--red)' : pct <= 65 ? 'var(--amber)' : 'var(--green)',
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

function SlaTicker({ sla_due_at, rfi_type }) {
  const [info, setInfo] = useState(() => getSlaInfo(sla_due_at, rfi_type));
  useEffect(() => {
    setInfo(getSlaInfo(sla_due_at, rfi_type));
    const t = setInterval(() => setInfo(getSlaInfo(sla_due_at, rfi_type)), 10000);
    return () => clearInterval(t);
  }, [sla_due_at, rfi_type]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '10px 14px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {sla_due_at
            ? `Due ${new Date(sla_due_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`
            : 'No deadline set'}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: info.color, fontFamily: "'JetBrains Mono', monospace" }}>
          {info.label} ({info.pct}%)
        </span>
      </div>
      <MiniProgressBar percent={info.pct} />
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

function ConsiderationCard({ c, index, initialDraft, currentStage }) {
  const [draft, setDraft] = useState('');
  const [draftRisk, setDraftRisk] = useState(null);
  const [drafting, setDrafting] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [draftError, setDraftError] = useState('');

  const canDraft = ['awaiting_response', 'drafting'].includes(currentStage);

  // Auto-load cached draft from DB on mount
  useEffect(() => {
    if (!c.id) return;
    getDraftHistory(c.id)
      .then(res => {
        const drafts = res?.drafts || [];
        if (drafts.length > 0) {
          const latest = drafts[drafts.length - 1];
          setDraft(latest.draft_text || '');
          setDraftRisk(latest.risk_score ?? null);
        } else if (initialDraft) {
          setDraft(initialDraft);
        }
      })
      .catch(() => {
        if (initialDraft) setDraft(initialDraft);
      });
  }, [c.id]);

  const handleDraft = async (force = false) => {
    if (drafting || !canDraft) return;
    setDrafting(true);
    setDraftError('');
    try {
      const result = await draftAiResponse(c.id, force);
      setDraft(result.draft_text);
      setDraftRisk(result.risk_score);
    } catch (err) {
      console.error('[ConsiderationCard] Drafting failed:', err);
      const msg = err?.detail || err?.message || 'Failed to generate draft.';
      setDraftError(msg);
    } finally {
      setDrafting(false);
    }
  };

  const handleEvaluateManual = async () => {
    if (evaluating || !canDraft || !draft) return;
    setEvaluating(true);
    setDraftError('');
    try {
      const result = await evaluateManualDraft(c.id, draft);
      setDraftRisk(result.risk_score);
    } catch (err) {
      console.error('[ConsiderationCard] Manual evaluation failed:', err);
      const msg = err?.detail || err?.message || 'Failed to evaluate draft risk.';
      setDraftError(msg);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div style={s.considerationCard}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={s.numBadge}>{c.number || index + 1}</div>
        {c.ctr_article_name && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.ctr_article_name}</div>
        )}
      </div>

      {c.concern_text ? (
        <div>
          <div style={s.textLabel}> Concern (NCA Question)</div>
          <div style={s.concernBlock}>{c.concern_text}</div>
        </div>
      ) : null}

      {c.outcome_status && (
        <div style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>
           Outcome: {c.outcome_status}
        </div>
      )}

      {/* AI Draft Section */}
      <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
        {canDraft ? (
          <button
            style={s.scoreBtn(drafting)}
            disabled={drafting || !c.concern_text || !c.id}
            onClick={() => handleDraft(Boolean(draft))}
          >
            {drafting ? 'Generating AI Draft...' : draft ? ' Regenerate Draft' : ' Draft Response'}
          </button>
        ) : (
          <div style={{ ...s.loadingText, fontStyle: 'normal', color: 'var(--text-dim)', fontSize: 12 }}>
             Draft available once stage is <strong>Awaiting Response</strong> or <strong>Drafting</strong>.
          </div>
        )}
        {draftError && (
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--red)', padding: '8px 12px', background: 'var(--red-light)', borderRadius: 'var(--radius-sm)' }}>
             {draftError}
          </div>
        )}

        {(draft || canDraft) && (
          <div style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <div style={{ ...s.textLabel, color: 'var(--accent-pink)' }}>AI Draft Response</div>
              <button
                style={{ ...s.scoreBtn(evaluating), padding: '4px 10px', fontSize: 11 }}
                disabled={evaluating || !draft || !c.id}
                onClick={handleEvaluateManual}
              >
                {evaluating ? 'Evaluating...' : '⚖️ Evaluate Risk'}
              </button>
            </div>
            <textarea 
              style={s.draftTextarea}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Click '✨ Draft Response' to generate with AI, or type your response manually here..."
            />
          </div>
        )}

        {draftRisk !== null && draftRisk !== undefined && (
          <div style={{ marginTop: 14 }}>
            <div style={{ ...s.textLabel, marginBottom: 8 }}>Risk Assessment (Acceptance Probability)</div>
            <div style={{ ...s.riskBarTrack, marginBottom: 6 }}>
              <div style={s.acceptanceBarFill(Math.round(draftRisk * 100))} />
            </div>
            <div style={s.acceptancePct(Math.round(draftRisk * 100))}>
              {Math.round(draftRisk * 100)}% Probability of Acceptance
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DetailPanel({ rfi, onClose, onStageAdvanced }) {
  const [advancing, setAdvancing] = useState(false);
  const [stageMsg, setStageMsg] = useState('');
  const [stageMsgOk, setStageMsgOk] = useState(true);
  const [currentStage, setCurrentStage] = useState(rfi.workflow_state?.current_stage || rfi.status || 'received');
  const [recommendations, setRecommendations] = useState([]);
  const [recsLoading, setRecsLoading] = useState(false);
  const [showSimilarModal, setShowSimilarModal] = useState(false);

  useEffect(() => {
    setCurrentStage(rfi.workflow_state?.current_stage || rfi.status || 'received');
  }, [rfi.id, rfi.workflow_state?.current_stage, rfi.status]);

  const currentIdx = STAGE_ORDER.indexOf(currentStage);

  // Load similar past responses
  useEffect(() => {
    const firstConcern = rfi.considerations?.find(c => c.concern_text)?.concern_text;
    if (!firstConcern) { setRecommendations([]); return; }
    setRecsLoading(true);
    searchRecommend(firstConcern, 3)
      .then(res => setRecommendations(res.results || []))
      .catch(err => { console.error('[DetailPanel] Recommendations fetch failed:', err); setRecommendations([]); })
      .finally(() => setRecsLoading(false));
  }, [rfi.id]);

  const advanceToNext = useCallback(async () => {
    const nextStage = STAGE_ORDER[currentIdx + 1];
    if (!nextStage || advancing) return;
    setAdvancing(true);
    setStageMsg('');
    try {
      const updatedRfi = await advanceRfiStage(rfi.id, nextStage);
      const newStage = updatedRfi.workflow_state?.current_stage || updatedRfi.status || nextStage;
      setCurrentStage(newStage);
      setStageMsgOk(true);
      setStageMsg(`Advanced to ${STAGE_LABELS[newStage]}`);
      onStageAdvanced?.(updatedRfi);
    } catch (err) {
      console.error('[DetailPanel] Stage advance failed:', err);
      setStageMsgOk(false);
      setStageMsg('Could not advance stage — check Layer 2 is running.');
    } finally {
      setAdvancing(false);
    }
  }, [rfi.id, currentIdx, advancing, onStageAdvanced]);

  // Collect best suggested draft text from recommendations
  const suggestedDraft = recommendations[0]?.response_text || '';

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
             Close
          </button>
        </div>

        <div style={s.body}>

          {/* SLA */}
          <div>
            <div style={s.sectionTitle}>⏱ Time Remaining</div>
            <SlaTicker sla_due_at={rfi.workflow_state?.sla_due_at} rfi_type={rfi.rfi_type} />
          </div>

          <div style={s.divider} />

          {/* Details */}
          <div>
            <div style={s.sectionTitle}> Details</div>
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

          {/* Considerations */}
          {rfi.considerations?.length > 0 && (
            <div>
              <div style={s.sectionTitle}> Considerations ({rfi.considerations.length})</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {rfi.considerations.map((c, i) => (
                  <ConsiderationCard key={c.id || i} c={c} index={i} initialDraft={i === 0 ? suggestedDraft : ''} currentStage={currentStage} />
                ))}
              </div>
            </div>
          )}

          {/* Similar Past Responses */}
          <div>
            <div style={s.sectionTitle}> Similar Past Responses</div>
            {recsLoading ? (
              <div style={s.loadingText}>Searching regulatory memory…</div>
            ) : (() => {
              if (recommendations.length === 0) {
                return (
                  <div style={{ ...s.loadingText, padding: '12px 16px', background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', color: 'var(--text-dim)', fontStyle: 'normal' }}>
                    No similar past responses found.
                  </div>
                );
              }

              return (
                <div>
                  <button
                    onClick={() => setShowSimilarModal(true)}
                    style={s.scoreBtn(false)}
                    onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 14px rgba(240,98,146,0.45)'; }}
                    onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 2px 10px rgba(240,98,146,0.3)'; }}
                  >
                    View Similar ({recommendations.length})
                  </button>
                </div>
              );
            })()}
          </div>

          {/* Workflow Stage */}
          <div>
            <div style={s.sectionTitle}> Workflow Stage</div>
            <div style={s.stageWrap}>
              {STAGE_ORDER.map((stage, idx) => (
                <div key={stage} style={s.stagePill(idx === currentIdx, idx < currentIdx)}>
                  {idx < currentIdx ? ' ' : ''}{STAGE_LABELS[stage]}
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
                 This RFI has been fully submitted.
              </div>
            )}
          </div>

        </div>
      </div>
      {showSimilarModal && (
        <SimilarResponsesModal
          recommendations={recommendations}
          onClose={() => setShowSimilarModal(false)}
        />
      )}
    </div>
  );
}
