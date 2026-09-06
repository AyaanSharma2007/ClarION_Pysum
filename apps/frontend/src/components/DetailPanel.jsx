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
  if (!sla_due_at) return { label: 'No SLA set', color: 'var(--text-dim)', bg: '#f4f6fb', pct: 0 };
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

const s = {
  overlay: {
    position: 'fixed',
    top: 0, right: 0, bottom: 0, left: 0,
    background: 'rgba(26,29,46,0.32)',
    backdropFilter: 'blur(2px)',
    zIndex: 100,
    display: 'flex',
    justifyContent: 'flex-end',
  },
  panel: {
    width: 540,
    maxWidth: '100vw',
    background: '#ffffff',
    borderLeft: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
    animation: 'slideInRight 0.22s ease',
    boxShadow: '-8px 0 40px rgba(79,114,255,0.10)',
  },
  header: {
    padding: '22px 28px',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
    position: 'sticky',
    top: 0,
    background: '#ffffff',
    zIndex: 1,
  },
  rfiId: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
    fontWeight: 700,
    color: 'var(--text)',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: 'var(--text-muted)',
  },
  closeBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '6px 12px',
    fontSize: 12,
    flexShrink: 0,
    transition: 'all 0.15s',
  },
  body: {
    padding: '22px 28px',
    display: 'flex',
    flexDirection: 'column',
    gap: 22,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.10em',
    color: 'var(--text-dim)',
    marginBottom: 8,
  },
  slaCard: (color, bg) => ({
    background: bg,
    borderRadius: 'var(--radius-md)',
    padding: '16px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    border: `1px solid ${color}33`,
  }),
  slaSmall: { fontSize: 11, color: 'var(--text-muted)' },
  slaDeadline: { fontSize: 12, color: 'var(--text-dim)', marginTop: 2 },
  slaBig: (color) => ({
    fontSize: 18,
    fontWeight: 800,
    color,
    fontFamily: "'JetBrains Mono', monospace",
  }),
  metaGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 10,
  },
  metaBox: {
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '10px 14px',
  },
  metaLabel: {
    fontSize: 10,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginBottom: 3,
  },
  metaValue: { fontSize: 13, color: 'var(--text)', fontWeight: 500 },
  riskCard: {
    background: '#fff',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '16px 20px',
    boxShadow: 'var(--shadow-sm)',
  },
  riskScore: (score) => {
    const color = score >= 0.7 ? 'var(--red)' : score >= 0.4 ? 'var(--amber)' : 'var(--green)';
    return { fontSize: 32, fontWeight: 800, color, marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" };
  },
  riskBar: (score) => {
    const color = score >= 0.7 ? 'var(--red)' : score >= 0.4 ? 'var(--amber)' : 'var(--green)';
    const pct = Math.round(score * 100);
    return {
      height: 6,
      borderRadius: 3,
      background: `linear-gradient(to right, ${color} ${pct}%, var(--border) ${pct}%)`,
      marginTop: 8,
    };
  },
  riskNote: { fontSize: 11, color: 'var(--text-dim)', marginTop: 8 },
  considerationCard: {
    background: '#fff',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '16px 18px',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    boxShadow: 'var(--shadow-sm)',
  },
  numBadge: {
    width: 24, height: 24,
    borderRadius: '50%',
    background: 'var(--accent-blue-light)',
    color: 'var(--accent-blue)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 10,
    fontWeight: 700,
    flexShrink: 0,
  },
  articleName: { fontSize: 11, color: 'var(--text-muted)' },
  textLabel: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    color: 'var(--text-dim)',
    marginBottom: 4,
  },
  textBlock: {
    fontSize: 13,
    color: 'var(--text)',
    lineHeight: 1.65,
  },
  recommendCard: {
    background: 'var(--green-light)',
    border: '1px solid rgba(45,184,122,0.2)',
    borderRadius: 'var(--radius-md)',
    padding: '14px 18px',
    fontSize: 13,
    color: 'var(--text)',
    lineHeight: 1.65,
  },
  recommendLabel: {
    fontSize: 10,
    fontWeight: 700,
    color: 'var(--green)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 6,
  },
  divider: { height: 1, background: 'var(--border)', margin: '2px 0' },
  stageWrap: { display: 'flex', gap: 6, flexWrap: 'wrap' },
  stagePill: (active, done) => ({
    padding: '6px 12px',
    borderRadius: 20,
    fontSize: 11,
    fontWeight: active ? 700 : 500,
    border: `1.5px solid ${active ? 'var(--accent-blue)' : done ? 'rgba(45,184,122,0.3)' : 'var(--border)'}`,
    background: active ? 'var(--accent-blue)' : done ? 'var(--green-light)' : '#fff',
    color: active ? '#fff' : done ? 'var(--green)' : 'var(--text-dim)',
    transition: 'all 0.15s',
  }),
  advanceBtn: {
    marginTop: 10,
    padding: '11px',
    background: 'linear-gradient(135deg, var(--accent-blue) 0%, #6f8fff 100%)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    width: '100%',
    boxShadow: '0 2px 10px rgba(79,114,255,0.25)',
    transition: 'opacity 0.15s',
  },
  statusMsg: (ok) => ({
    fontSize: 12,
    color: ok ? 'var(--green)' : 'var(--red)',
    marginTop: 6,
    padding: '8px 12px',
    background: ok ? 'var(--green-light)' : 'var(--red-light)',
    borderRadius: 'var(--radius-sm)',
  }),
  loadingText: {
    fontSize: 12,
    color: 'var(--text-dim)',
    fontStyle: 'italic',
    padding: '12px 0',
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
        <div style={s.slaSmall}>Submission deadline</div>
        <div style={s.slaDeadline}>
          {sla_due_at
            ? new Date(sla_due_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
            : '—'}
        </div>
      </div>
      <div style={s.slaBig(info.color)}>{info.label}</div>
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

  useEffect(() => {
    setRisk(null);
    setRiskLoading(true);
    const features = {
      num_considerations: rfi.considerations?.length || 1,
      sla_window_hours: rfi.workflow_state?.sla_due_at
        ? Math.max(0, (new Date(rfi.workflow_state.sla_due_at) - Date.now()) / 3600000)
        : 72,
      is_hub_article: rfi.considerations?.some(c => c.is_hub_article) ? 1 : 0,
      country_risk_score: 0.5,
      category_risk_score: 0.5,
      days_since_received: rfi.received_at
        ? Math.floor((Date.now() - new Date(rfi.received_at)) / 86400000)
        : 0,
    };
    predictDossierRisk(features)
      .then(res => setRisk(res))
      .catch((err) => { console.error('[DetailPanel] Risk prediction failed:', err); setRisk(null); })
      .finally(() => setRiskLoading(false));
  }, [rfi.id]);

  useEffect(() => {
    const firstConcern = rfi.considerations?.find(c => c.concern_text)?.concern_text;
    if (!firstConcern) { setRecommendations([]); return; }
    setRecsLoading(true);
    searchSemantic(firstConcern, 2)
      .then(res => setRecommendations(res.results?.slice(0, 2) || []))
      .catch((err) => { console.error('[DetailPanel] Recommendations fetch failed:', err); setRecommendations([]); })
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
      setStageMsg('Could not advance stage — check that Layer 2 is running.');
    } finally {
      setAdvancing(false);
    }
  }, [rfi.id, currentIdx, advancing, onStageAdvanced]);

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
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            ✕ Close
          </button>
        </div>

        <div style={s.body}>
          {/* SLA */}
          <div>
            <div style={s.sectionTitle}>Time Remaining</div>
            <SlaTicker sla_due_at={rfi.workflow_state?.sla_due_at} />
          </div>

          <div style={s.divider} />

          {/* Details */}
          <div>
            <div style={s.sectionTitle}>Details</div>
            <div style={s.metaGrid}>
              {[
                ['Country', rfi.nca_country],
                ['Category', rfi.category],
                ['Submit Date', rfi.submit_date],
                ['Due Date', rfi.due_date],
              ].map(([label, value]) => (
                <div key={label} style={s.metaBox}>
                  <div style={s.metaLabel}>{label}</div>
                  <div style={s.metaValue}>{value || '—'}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={s.divider} />

          {/* Risk */}
          <div>
            <div style={s.sectionTitle}>Risk Assessment</div>
            <div style={s.riskCard}>
              {riskLoading ? (
                <div style={s.loadingText}>Calculating risk score…</div>
              ) : risk ? (
                <>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
                    Predicted non-compliance probability
                  </div>
                  <div style={s.riskScore(risk.risk_score ?? 0.5)}>
                    {risk.risk_score != null ? `${Math.round(risk.risk_score * 100)}%` : '—'}
                  </div>
                  <div style={s.riskBar(risk.risk_score ?? 0.5)} />
                  {risk.top_features?.length > 0 && (
                    <div style={s.riskNote}>
                      Key drivers: {risk.top_features.slice(0, 3).map(f => f.name || f).join(', ')}
                    </div>
                  )}
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
              <div style={s.sectionTitle}>
                Considerations ({rfi.considerations.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {rfi.considerations.map((c, i) => (
                  <div key={c.id || i} style={s.considerationCard}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={s.numBadge}>{c.number || i + 1}</div>
                      {c.ctr_article_name && <div style={s.articleName}>{c.ctr_article_name}</div>}
                    </div>
                    {c.concern_text && (
                      <div>
                        <div style={s.textLabel}>Concern</div>
                        <div style={s.textBlock}>{c.concern_text}</div>
                      </div>
                    )}
                    {c.response_text && (
                      <div>
                        <div style={s.textLabel}>Sponsor Response</div>
                        <div style={s.textBlock}>{c.response_text}</div>
                      </div>
                    )}
                    {c.outcome_status && (
                      <div style={{ fontSize: 11, color: 'var(--green)', fontWeight: 600 }}>
                        ✓ Outcome: {c.outcome_status}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Recommendations */}
          <div>
            <div style={s.sectionTitle}>Similar Past Responses</div>
            {recsLoading ? (
              <div style={s.loadingText}>Finding similar regulatory cases…</div>
            ) : recommendations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {recommendations.map((rec, i) => (
                  <div key={i} style={s.recommendCard}>
                    <div style={s.recommendLabel}>Similar Case #{i + 1} · Score {rec.score?.toFixed(2)}</div>
                    <div>
                      {rec.rfi?.considerations?.[0]?.response_text ||
                       rec.rfi?.rfi_text ||
                       'No response text available for this case.'}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ ...s.loadingText, background: 'var(--bg)', padding: '12px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                {rfi.considerations?.find(c => c.concern_text)
                  ? 'No similar cases found in the database yet.'
                  : 'No concern text available to search for similar cases.'}
              </div>
            )}
          </div>

          <div style={s.divider} />

          {/* Workflow Stage */}
          <div>
            <div style={s.sectionTitle}>Workflow Stage</div>
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
                  onMouseEnter={e => { if (!advancing) e.currentTarget.style.opacity = '0.88'; }}
                  onMouseLeave={e => { if (!advancing) e.currentTarget.style.opacity = '1'; }}
                >
                  {advancing ? 'Advancing…' : `Advance to ${STAGE_LABELS[STAGE_ORDER[currentIdx + 1]]}`}
                </button>
                {stageMsg && <div style={s.statusMsg(stageMsgOk)}>{stageMsg}</div>}
              </>
            ) : (
              <div style={{ ...s.statusMsg(true), marginTop: 10 }}>
                ✓ This RFI has been fully submitted.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
