import React, { useState, useEffect, useCallback } from 'react';
import { advanceRfiStage, predictDossierRisk, searchSemantic } from '../services/api';

const STAGE_ORDER = ['received', 'RA_Clinical_Review', 'CTA_Mgmt_Review', 'EU_Hub_Approval', 'Submitted'];
const STAGE_LABELS = {
  received: 'Received',
  RA_Clinical_Review: 'RA Clinical Review',
  CTA_Mgmt_Review: 'CTA Management Review',
  EU_Hub_Approval: 'EU Hub Approval',
  Submitted: 'Submitted',
};

function getSlaInfo(sla_due_at) {
  if (!sla_due_at) return { label: 'No SLA', color: 'var(--text-dim)', pct: 0 };
  const now = Date.now();
  const due = new Date(sla_due_at).getTime();
  const totalMs = 72 * 60 * 60 * 1000;
  const diffMs = due - now;
  if (diffMs <= 0) return { label: 'OVERDUE', color: 'var(--red)', pct: 0 };
  const hours = Math.floor(diffMs / 3600000);
  const mins = Math.floor((diffMs % 3600000) / 60000);
  const pct = Math.min(100, Math.round((diffMs / totalMs) * 100));
  const label = hours > 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h remaining` : `${hours}h ${mins}m remaining`;
  const color = pct > 50 ? 'var(--green)' : pct > 20 ? 'var(--amber)' : 'var(--red)';
  return { label, color, pct };
}

const s = {
  overlay: {
    position: 'fixed',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    background: 'rgba(0,0,0,0.5)',
    zIndex: 100,
    display: 'flex',
    justifyContent: 'flex-end',
  },
  panel: {
    width: 520,
    maxWidth: '100vw',
    background: '#0d0d0d',
    borderLeft: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
    animation: 'slideInRight 0.2s ease',
  },
  header: {
    padding: '20px 24px',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
    position: 'sticky',
    top: 0,
    background: '#0d0d0d',
    zIndex: 1,
  },
  rfiId: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 13,
    fontWeight: 700,
    color: '#e5e5e5',
    marginBottom: 4,
  },
  closeBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 6,
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '5px 10px',
    fontSize: 13,
    flexShrink: 0,
    transition: 'border-color 0.15s, color 0.15s',
  },
  body: {
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    color: 'var(--text-dim)',
    marginBottom: 2,
  },
  metaGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 8,
  },
  metaBox: {
    background: '#111',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '10px 14px',
  },
  metaLabel: {
    fontSize: 10,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginBottom: 3,
  },
  metaValue: {
    fontSize: 13,
    color: '#e5e5e5',
    fontWeight: 500,
  },
  slaBox: (color) => ({
    background: '#111',
    border: `1px solid ${color === 'var(--red)' ? 'rgba(239,68,68,0.3)' : color === 'var(--amber)' ? 'rgba(245,158,11,0.3)' : 'rgba(34,197,94,0.2)'}`,
    borderRadius: 8,
    padding: '12px 16px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  }),
  slaLabel: {
    fontSize: 11,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  slaValue: (color) => ({
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 16,
    fontWeight: 700,
    color,
  }),
  considerationCard: {
    background: '#111',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '14px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  considerationNum: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  numBadge: {
    width: 22,
    height: 22,
    borderRadius: '50%',
    background: 'rgba(59,130,246,0.1)',
    border: '1px solid rgba(59,130,246,0.2)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 10,
    fontWeight: 700,
    color: '#60a5fa',
    flexShrink: 0,
  },
  articleName: {
    fontSize: 11,
    color: 'var(--text-muted)',
  },
  textBlock: (subtle) => ({
    fontSize: 13,
    color: subtle ? 'var(--text-muted)' : '#ddd',
    lineHeight: 1.6,
    fontStyle: subtle ? 'italic' : 'normal',
  }),
  textLabel: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    color: 'var(--text-dim)',
    marginBottom: 4,
  },
  riskBox: {
    background: '#111',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '14px 16px',
  },
  riskScore: (score) => {
    const color = score >= 0.7 ? 'var(--red)' : score >= 0.4 ? 'var(--amber)' : 'var(--green)';
    return {
      fontSize: 28,
      fontWeight: 800,
      fontFamily: "'JetBrains Mono', monospace",
      color,
      marginBottom: 4,
    };
  },
  riskBar: (score) => {
    const color = score >= 0.7 ? 'var(--red)' : score >= 0.4 ? 'var(--amber)' : 'var(--green)';
    const pct = Math.round(score * 100);
    return {
      height: 4,
      borderRadius: 2,
      background: `linear-gradient(to right, ${color} ${pct}%, #1e1e1e ${pct}%)`,
      marginTop: 6,
    };
  },
  recommendBox: {
    background: 'rgba(34,197,94,0.04)',
    border: '1px solid rgba(34,197,94,0.15)',
    borderRadius: 8,
    padding: '14px 16px',
    fontSize: 13,
    color: '#d4d4d4',
    lineHeight: 1.65,
  },
  divider: {
    height: 1,
    background: 'var(--border)',
  },
  stageRow: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap',
  },
  stageBtn: (active, done) => ({
    padding: '7px 12px',
    borderRadius: 6,
    border: `1px solid ${active ? '#fff' : done ? 'rgba(34,197,94,0.3)' : 'var(--border)'}`,
    background: active ? '#fff' : done ? 'rgba(34,197,94,0.06)' : 'transparent',
    color: active ? '#000' : done ? '#4ade80' : 'var(--text-dim)',
    fontSize: 11,
    fontWeight: active ? 700 : 500,
    cursor: active ? 'default' : 'pointer',
    transition: 'all 0.15s',
  }),
  advanceBtn: {
    marginTop: 8,
    padding: '10px',
    background: '#fff',
    color: '#000',
    border: 'none',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
    width: '100%',
    transition: 'opacity 0.15s',
  },
  msg: (ok) => ({
    fontSize: 12,
    color: ok ? 'var(--green)' : 'var(--red)',
    marginTop: 6,
    fontFamily: "'JetBrains Mono', monospace",
  }),
  loadingText: {
    fontSize: 12,
    color: 'var(--text-dim)',
    fontStyle: 'italic',
  },
};

// SLA countdown that ticks live
function SlaTicker({ sla_due_at }) {
  const [info, setInfo] = useState(() => getSlaInfo(sla_due_at));
  useEffect(() => {
    const t = setInterval(() => setInfo(getSlaInfo(sla_due_at)), 10000);
    return () => clearInterval(t);
  }, [sla_due_at]);

  return (
    <div style={s.slaBox(info.color)}>
      <div>
        <div style={s.slaLabel}>SLA Deadline</div>
        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
          {sla_due_at ? new Date(sla_due_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
        </div>
      </div>
      <div style={s.slaValue(info.color)}>{info.label}</div>
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

  // Load risk prediction
  useEffect(() => {
    setRisk(null);
    setRiskLoading(true);
    const features = {
      num_considerations: rfi.considerations?.length || 1,
      sla_window_hours: rfi.workflow_state?.sla_due_at
        ? Math.max(0, (new Date(rfi.workflow_state.sla_due_at) - Date.now()) / 3600000)
        : 72,
      is_hub_article: rfi.considerations?.some(c => c.is_hub_article) ? 1 : 0,
      country_risk_score: 0.5, // placeholder
      category_risk_score: 0.5,
      days_since_received: rfi.received_at
        ? Math.floor((Date.now() - new Date(rfi.received_at)) / 86400000)
        : 0,
    };
    predictDossierRisk(features)
      .then(res => setRisk(res))
      .catch(() => setRisk(null))
      .finally(() => setRiskLoading(false));
  }, [rfi.id]);

  // Load recommendations from first concern text
  useEffect(() => {
    const firstConcern = rfi.considerations?.find(c => c.concern_text)?.concern_text;
    if (!firstConcern) { setRecommendations([]); return; }
    setRecsLoading(true);
    searchSemantic(firstConcern, 2)
      .then(res => setRecommendations(res.results?.slice(0, 2) || []))
      .catch(() => setRecommendations([]))
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
      setStageMsg(`✓ Advanced to ${STAGE_LABELS[nextStage]}`);
      onStageAdvanced?.();
    } catch {
      setStageMsgOk(false);
      setStageMsg('Failed — check Layer 2 is running');
    } finally {
      setAdvancing(false);
    }
  }, [rfi.id, currentIdx, advancing, onStageAdvanced]);

  // Click outside to close
  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div style={s.overlay} onClick={handleOverlayClick}>
      <div style={s.panel}>
        {/* Header */}
        <div style={s.header}>
          <div>
            <div style={s.rfiId}>{rfi.rfi_id}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {rfi.nca_country} · {rfi.therapeutic_area_name || rfi.indication?.name || '—'}
            </div>
          </div>
          <button
            id="detail-panel-close"
            style={s.closeBtn}
            onClick={onClose}
            onMouseEnter={e => { e.target.style.borderColor = '#555'; e.target.style.color = '#ddd'; }}
            onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = 'var(--text-muted)'; }}
          >
            ✕ Close
          </button>
        </div>

        <div style={s.body}>
          {/* SLA */}
          <div style={s.section}>
            <div style={s.sectionTitle}>Time Remaining</div>
            <SlaTicker sla_due_at={rfi.workflow_state?.sla_due_at} />
          </div>

          <div style={s.divider} />

          {/* Key Details */}
          <div style={s.section}>
            <div style={s.sectionTitle}>Details</div>
            <div style={s.metaGrid}>
              <div style={s.metaBox}>
                <div style={s.metaLabel}>Country</div>
                <div style={s.metaValue}>{rfi.nca_country || '—'}</div>
              </div>
              <div style={s.metaBox}>
                <div style={s.metaLabel}>Category</div>
                <div style={s.metaValue}>{rfi.category || '—'}</div>
              </div>
              <div style={s.metaBox}>
                <div style={s.metaLabel}>Submit Date</div>
                <div style={s.metaValue}>{rfi.submit_date || '—'}</div>
              </div>
              <div style={s.metaBox}>
                <div style={s.metaLabel}>Due Date</div>
                <div style={s.metaValue}>{rfi.due_date || '—'}</div>
              </div>
            </div>
          </div>

          <div style={s.divider} />

          {/* Risk Score */}
          <div style={s.section}>
            <div style={s.sectionTitle}>Risk Assessment</div>
            <div style={s.riskBox}>
              {riskLoading ? (
                <div style={s.loadingText}>Calculating risk score…</div>
              ) : risk ? (
                <>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 6 }}>
                    Predicted non-compliance probability
                  </div>
                  <div style={s.riskScore(risk.risk_score ?? 0.5)}>
                    {risk.risk_score != null ? `${Math.round(risk.risk_score * 100)}%` : '—'}
                  </div>
                  <div style={s.riskBar(risk.risk_score ?? 0.5)} />
                  {risk.top_features && risk.top_features.length > 0 && (
                    <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-dim)' }}>
                      Key drivers: {risk.top_features.slice(0, 3).map(f => f.name || f).join(', ')}
                    </div>
                  )}
                </>
              ) : (
                <div style={s.loadingText}>Risk model unavailable — start Layer 1 backend.</div>
              )}
            </div>
          </div>

          <div style={s.divider} />

          {/* Considerations */}
          {rfi.considerations?.length > 0 && (
            <div style={s.section}>
              <div style={s.sectionTitle}>
                Considerations ({rfi.considerations.length})
              </div>
              {rfi.considerations.map((c, i) => (
                <div key={c.id || i} style={s.considerationCard}>
                  <div style={s.considerationNum}>
                    <div style={s.numBadge}>{c.number || i + 1}</div>
                    {c.ctr_article_name && (
                      <div style={s.articleName}>{c.ctr_article_name}</div>
                    )}
                  </div>

                  {c.concern_text && (
                    <div>
                      <div style={s.textLabel}>Concern</div>
                      <div style={s.textBlock(false)}>{c.concern_text}</div>
                    </div>
                  )}

                  {c.response_text && (
                    <div>
                      <div style={s.textLabel}>Sponsor Response</div>
                      <div style={s.textBlock(false)}>{c.response_text}</div>
                    </div>
                  )}

                  {c.outcome_status && (
                    <div style={{ fontSize: 11, color: 'var(--green)' }}>
                      Outcome: {c.outcome_status}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* AI Recommended Response */}
          <div style={s.section}>
            <div style={s.sectionTitle}>AI — Similar Past Responses</div>
            {recsLoading ? (
              <div style={s.loadingText}>Finding similar regulatory cases…</div>
            ) : recommendations.length > 0 ? (
              recommendations.map((rec, i) => (
                <div key={i} style={s.recommendBox}>
                  <div style={{ fontSize: 10, color: 'var(--green)', fontWeight: 700, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Similar Case #{i + 1} · Score {rec.score?.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 13, color: '#d4d4d4', lineHeight: 1.65 }}>
                    {rec.rfi?.considerations?.[0]?.response_text ||
                     rec.rfi?.rfi_text ||
                     'No response text available for this case.'}
                  </div>
                </div>
              ))
            ) : (
              <div style={{ ...s.loadingText, padding: '12px 16px', background: '#111', border: '1px solid var(--border)', borderRadius: 8 }}>
                {rfi.considerations?.find(c => c.concern_text)
                  ? 'No similar cases found in the database yet.'
                  : 'No concern text available to find similar cases.'}
              </div>
            )}
          </div>

          <div style={s.divider} />

          {/* Workflow Stage */}
          <div style={s.section}>
            <div style={s.sectionTitle}>Workflow Stage</div>
            <div style={s.stageRow}>
              {STAGE_ORDER.map((stage, idx) => (
                <div key={stage} style={s.stageBtn(idx === currentIdx, idx < currentIdx)}>
                  {idx < currentIdx ? '✓ ' : ''}{STAGE_LABELS[stage]}
                </div>
              ))}
            </div>

            {currentIdx < STAGE_ORDER.length - 1 && (
              <>
                <button
                  id="advance-stage-btn"
                  style={{ ...s.advanceBtn, opacity: advancing ? 0.6 : 1 }}
                  disabled={advancing}
                  onClick={advanceToNext}
                >
                  {advancing ? 'Advancing…' : `Advance to ${STAGE_LABELS[STAGE_ORDER[currentIdx + 1]]}`}
                </button>
                {stageMsg && <div style={s.msg(stageMsgOk)}>{stageMsg}</div>}
              </>
            )}

            {currentIdx === STAGE_ORDER.length - 1 && (
              <div style={{ fontSize: 12, color: 'var(--green)', marginTop: 4 }}>
                ✓ This RFI has been fully submitted.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
