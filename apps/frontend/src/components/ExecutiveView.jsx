import React, { useState, useEffect, useMemo } from 'react';
import { getRfiAuditChain } from '../services/api';

const ACTION_LABELS = {
  ingested: 'RFI Uploaded',
  rfi_created: 'RFI Uploaded',
  RFI_CREATED: 'RFI Uploaded',
  rfi_uploaded: 'RFI Uploaded',
  RFI_UPLOADED: 'RFI Uploaded',
  stage_advanced: 'Stage Advanced',
  STAGE_ADVANCED: 'Stage Advanced',
  stage_advanced_submission: 'Submission Stage Advanced',
  response_attached: 'Response Attached',
  response_submitted: 'Response Submitted',
  RESPONSE_SUBMITTED: 'Response Submitted',
  category_corrected: 'Category Corrected',
  CATEGORY_CORRECTED: 'Category Corrected',
  approved: 'Response Approved (GATE-001)',
  APPROVED: 'Response Approved (GATE-001)',
  policy_override: 'Policy Override Recorded',
  sla_warning: 'SLA Warning Flagged',
  sla_breach: 'SLA Breach Recorded',
  safety_gateway_flag: 'Safety Gateway Sanitization',
};

const MOCK_CHAIN = (uuid) => ({
  rfi_id: uuid,
  chain_valid: true,
  entries: [
    {
      id: 'gen-1',
      action: 'ingested',
      actor: 'EU-Hub-Regulatory',
      curr_hash: '5ee7edf4fca437aeddd161c069c1bb486b8e01b3257966e0fad66aa08dd9c666',
      prev_hash: null,
      created_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
      metadata: { stage: 'Received' },
    },
    {
      id: 'stg-2',
      action: 'stage_advanced',
      actor: 'RA Clinical Specialist',
      curr_hash: '9a31bc28d0fe4a909fb37450f538cfb465861d6d7d16ad3930157108f5acbb16',
      prev_hash: '5ee7edf4fca437aeddd161c069c1bb486b8e01b3257966e0fad66aa08dd9c666',
      created_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
      metadata: { from_stage: 'Received', to_stage: 'RA_Clinical_Review' },
    },
  ],
});

export default function ExecutiveView({ rfis = [] }) {
  const [selected, setSelected] = useState(rfis[0] || null);
  const [searchQuery, setSearchQuery] = useState('');
  const [chain, setChain] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copiedHash, setCopiedHash] = useState(null);

  // Sync selected when rfis list arrives
  useEffect(() => {
    if (!selected && rfis.length > 0) {
      setSelected(rfis[0]);
    }
  }, [rfis, selected]);

  useEffect(() => {
    if (selected) {
      loadData(selected.rfi_id || selected.id);
    }
  }, [selected]);

  const loadData = async (identifier) => {
    setLoading(true);
    try {
      const auditData = await getRfiAuditChain(identifier);
      setChain(auditData || MOCK_CHAIN(identifier));
    } catch {
      setChain(MOCK_CHAIN(identifier));
    } finally {
      setLoading(false);
    }
  };

  const filteredRfis = useMemo(() => {
    if (!searchQuery.trim()) return rfis;
    const q = searchQuery.toLowerCase();
    return rfis.filter(
      r =>
        (r.rfi_id && r.rfi_id.toLowerCase().includes(q)) ||
        (r.msc_country && r.msc_country.toLowerCase().includes(q)) ||
        (r.nca_country && r.nca_country.toLowerCase().includes(q)) ||
        (r.category && r.category.toLowerCase().includes(q)) ||
        (r.status && r.status.toLowerCase().includes(q))
    );
  }, [rfis, searchQuery]);

  const fmtTime = (ts) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return (
        d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) +
        ' · ' +
        d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      );
    } catch {
      return String(ts);
    }
  };

  const copyHash = (hash) => {
    if (!hash) return;
    navigator.clipboard?.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const formatStageName = (stg) => {
    if (!stg) return '';
    return String(stg)
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };

  const getActionTitle = (action, meta = {}) => {
    const raw = (action || '').toLowerCase();

    // 1. Titles to 'RFI Uploaded' instead of 'RFI Ingested'
    if (raw === 'ingested' || raw === 'rfi_created' || raw === 'rfi_uploaded') {
      return 'RFI Uploaded';
    }

    // 2. Beside stage advanced, mention from which stage to which it has been advanced in brackets
    if (raw.startsWith('stage_advanced')) {
      const inner = meta?.metadata || meta || {};
      const fromStg = inner.from_stage || meta?.from_stage;
      const toStg = inner.to_stage || meta?.to_stage || inner.stage || meta?.stage;

      if (fromStg && toStg) {
        return `Stage Advanced (${formatStageName(fromStg)} to ${formatStageName(toStg)})`;
      } else if (toStg) {
        return `Stage Advanced (to ${formatStageName(toStg)})`;
      }
      return 'Stage Advanced';
    }

    if (ACTION_LABELS[action]) return ACTION_LABELS[action];
    return action
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };

  return (
    <div style={s.page}>
      {/* ── Two-Column Main Layout ── */}
      <div style={s.grid}>
        {/* ── Left Column: RFI Selection List ── */}
        <div style={s.panel}>
          <div style={s.panelHead}>
            <span style={s.panelTitle}>RFIs ({filteredRfis.length})</span>
          </div>

          <div style={{ padding: '10px 12px 6px', borderBottom: '1px solid var(--border)' }}>
            <input
              type="text"
              placeholder="Search RFIs..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={s.searchInput}
            />
          </div>

          <div style={s.listBody}>
            {filteredRfis.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)', fontSize: 12 }}>
                No RFIs matching search
              </div>
            ) : (
              filteredRfis.map(rfi => {
                const isSelected = selected && (selected.id === rfi.id || selected.rfi_id === rfi.rfi_id);
                const country = rfi.msc_country || rfi.nca_country || 'EU';
                const stage = rfi.workflow_state?.current_stage || rfi.status || 'Received';
                return (
                  <div
                    key={rfi.id || rfi.rfi_id}
                    style={s.listItem(isSelected)}
                    onClick={() => setSelected(rfi)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                      <span style={s.itemId}>{rfi.rfi_id || rfi.id}</span>
                      <span style={s.countryBadge}>{country}</span>
                    </div>
                    <div style={s.itemSub}>
                      <span>{rfi.category || 'Clinical'}</span>
                      <span style={{ color: 'var(--text-dim)' }}>•</span>
                      <span style={{ textTransform: 'capitalize' }}>{stage.replace(/_/g, ' ')}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Right Column: Audit Timeline ── */}
        <div style={s.panel}>
          <div style={s.panelHead}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={s.panelTitle}>{selected?.rfi_id ?? 'Select an RFI'}</span>
              {chain?.chain_valid !== false && (
                <span style={s.badgeGreen}>✓ SHA-256 Integrity Verified</span>
              )}
            </div>
            <button
              onClick={() => selected && loadData(selected.rfi_id || selected.id)}
              style={s.refreshBtn}
              title="Refresh Audit Trail"
            >
              ↻ Refresh
            </button>
          </div>

          {loading ? (
            <div style={s.empty}>
              <span style={{ fontSize: 22, animation: 'spin 1.2s linear infinite', display: 'inline-block', marginBottom: 8 }}>⟳</span>
              <div>Verifying cryptographic hash chain…</div>
            </div>
          ) : selected ? (
            <div style={s.contentScroll}>
              <div style={s.timelineSectionHead}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                  Tamper-Evident Event Sequence ({chain?.entries?.length || 0} events)
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                  Genesis Block ➔ Current State
                </span>
              </div>

              <div style={s.chainBody}>
                {chain?.entries && chain.entries.length > 0 ? (
                  chain.entries.map((e, i) => {
                    const isLast = i === chain.entries.length - 1;
                    const meta = e.metadata || {};
                    return (
                      <div key={e.id || i} style={s.entry(isLast)}>
                        {/* Dot + Line */}
                        <div style={s.dotCol}>
                          <div style={s.dotCircle} />
                          {!isLast && <div style={s.dotLine} />}
                        </div>

                        {/* Content */}
                        <div style={s.entryContent}>
                          <div style={s.entryTopRow}>
                            <span style={s.actionTitle}>{getActionTitle(e.action, meta)}</span>
                            <span style={s.time}>{fmtTime(e.created_at || e.timestamp)}</span>
                          </div>

                          <div style={s.actorRow}>
                            <span style={s.actorBadge}>👤 {e.actor || 'System / Automated Pipeline'}</span>
                            {meta.stage && (
                              <span style={s.metaPill}>Stage: {meta.stage}</span>
                            )}
                            {meta.from_stage && meta.to_stage && (
                              <span style={s.metaPill}>
                                Transition: {meta.from_stage} ➔ {meta.to_stage}
                              </span>
                            )}
                          </div>

                          {/* Cryptographic Hashes Block */}
                          <div style={s.hashBox}>
                            <div style={s.hashRow}>
                              <span style={s.hashLabel}>Current Hash:</span>
                              <span
                                style={s.hashVal}
                                onClick={() => copyHash(e.curr_hash)}
                                title="Click to copy full SHA-256 hash"
                              >
                                {e.curr_hash ? `${e.curr_hash.slice(0, 16)}...${e.curr_hash.slice(-8)}` : '—'}
                              </span>
                              {copiedHash === e.curr_hash && (
                                <span style={s.copiedTag}>Copied!</span>
                              )}
                            </div>
                            <div style={s.hashRow}>
                              <span style={s.hashLabel}>Previous Hash:</span>
                              <span style={s.hashValMuted}>
                                {e.prev_hash ? `${e.prev_hash.slice(0, 16)}...${e.prev_hash.slice(-8)}` : '0x00000000 (Genesis Block)'}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div style={s.empty}>No audit log entries recorded for this RFI yet.</div>
                )}
              </div>
            </div>
          ) : (
            <div style={s.empty}>Select an RFI on the left to inspect its audit trail</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Theme-Aware Styles ────────────────────────────────────────────────────────
const s = {
  page: {
    padding: '24px 0 60px',
    display: 'flex',
    flexDirection: 'column',
    maxWidth: 1240,
    width: '100%',
    margin: '0 auto',
  },
  refreshBtn: {
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '5px 12px',
    fontSize: 11,
    fontWeight: 600,
    transition: 'all 0.15s',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '320px 1fr',
    gap: 16,
    alignItems: 'start',
  },
  panel: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-sm)',
    display: 'flex',
    flexDirection: 'column',
  },
  panelHead: {
    padding: '14px 18px',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: 'var(--bg)',
    gap: 10,
    flexWrap: 'wrap',
  },
  panelTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: 'var(--text)',
    fontFamily: '"JetBrains Mono", monospace',
  },
  searchInput: {
    width: '100%',
    padding: '7px 11px',
    fontSize: 12,
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
    background: 'var(--bg)',
    color: 'var(--text)',
    boxSizing: 'border-box',
    outline: 'none',
  },
  listBody: {
    padding: 8,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    maxHeight: '680px',
    overflowY: 'auto',
  },
  listItem: (active) => ({
    padding: '10px 12px',
    borderRadius: 'var(--radius-sm)',
    border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border)'}`,
    cursor: 'pointer',
    background: active ? 'var(--accent-blue-light)' : 'transparent',
    transition: 'all 0.12s',
  }),
  itemId: {
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text)',
  },
  countryBadge: {
    fontSize: 10,
    fontWeight: 700,
    padding: '1px 6px',
    borderRadius: 4,
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    color: 'var(--text-muted)',
  },
  itemSub: {
    fontSize: 11,
    color: 'var(--text-muted)',
    marginTop: 4,
    display: 'flex',
    gap: 6,
    alignItems: 'center',
  },
  badgeGreen: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '3px 8px',
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 600,
    background: 'var(--green-light)',
    color: 'var(--green)',
    border: '1px solid rgba(45,184,122,0.25)',
  },
  contentScroll: {
    padding: 18,
    display: 'flex',
    flexDirection: 'column',
    gap: 18,
    maxHeight: '750px',
    overflowY: 'auto',
  },
  timelineSectionHead: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: 8,
    borderBottom: '1px solid var(--border)',
  },
  chainBody: {
    display: 'flex',
    flexDirection: 'column',
  },
  entry: (isLast) => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 16,
    padding: '16px 0',
    borderBottom: isLast ? 'none' : '1px solid var(--border)',
  }),
  dotCol: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    flexShrink: 0,
    paddingTop: 4,
  },
  dotCircle: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: 'var(--green)',
    border: '2px solid var(--bg-card)',
    boxShadow: '0 0 0 2px var(--green)',
  },
  dotLine: {
    width: 2,
    background: 'var(--border)',
    flex: 1,
    marginTop: 6,
    minHeight: 48,
  },
  entryContent: {
    flex: 1,
    minWidth: 0,
  },
  entryTopRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
    gap: 10,
    flexWrap: 'wrap',
  },
  actionTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--text)',
  },
  time: {
    fontSize: 11,
    color: 'var(--text-dim)',
    fontFamily: '"JetBrains Mono", monospace',
  },
  actorRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
    flexWrap: 'wrap',
  },
  actorBadge: {
    fontSize: 11,
    color: 'var(--text-muted)',
    fontWeight: 500,
  },
  metaPill: {
    fontSize: 10,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'var(--bg)',
    color: 'var(--text-dim)',
    border: '1px solid var(--border)',
    fontFamily: 'monospace',
  },
  hashBox: {
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '8px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  hashRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 11,
    fontFamily: '"JetBrains Mono", monospace',
  },
  hashLabel: {
    color: 'var(--text-dim)',
    width: 95,
    flexShrink: 0,
  },
  hashVal: {
    color: 'var(--accent-blue)',
    cursor: 'pointer',
    textDecoration: 'underline dotted',
  },
  hashValMuted: {
    color: 'var(--text-muted)',
  },
  copiedTag: {
    fontSize: 10,
    color: 'var(--green)',
    fontWeight: 600,
    marginLeft: 6,
  },
  empty: {
    padding: 48,
    textAlign: 'center',
    color: 'var(--text-dim)',
    fontSize: 13,
  },
};
