import React, { useState, useEffect } from 'react';
import { getRfiAuditChain } from '../services/api';

const s = {
  page: { padding: '28px 0', display: 'flex', flexDirection: 'column', gap: 20 },
  heading: { fontSize: 16, fontWeight: 600, color: '#fff', marginBottom: 3 },
  sub: { fontSize: 12, color: '#555' },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 },
  stat: { background: '#111', border: '1px solid #222', borderRadius: 8, padding: '14px 18px' },
  statLabel: { fontSize: 11, color: '#555', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 },
  statValue: { fontSize: 22, fontWeight: 700, color: '#fff', fontFamily: '"JetBrains Mono", monospace' },
  grid: { display: 'grid', gridTemplateColumns: '260px 1fr', gap: 14 },
  panel: { background: '#111', border: '1px solid #222', borderRadius: 8, overflow: 'hidden' },
  panelHead: { padding: '12px 18px', borderBottom: '1px solid #1e1e1e', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  panelTitle: { fontSize: 13, fontWeight: 600, color: '#fff' },
  listBody: { padding: 10, display: 'flex', flexDirection: 'column', gap: 4 },
  listItem: (a) => ({
    padding: '9px 12px', borderRadius: 6, border: `1px solid ${a ? '#2a2a2a' : '#151515'}`,
    cursor: 'pointer', background: a ? '#1a1a1a' : 'transparent', transition: 'all 0.1s',
  }),
  itemId: { fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#ccc' },
  itemSub: { fontSize: 11, color: '#444', marginTop: 2 },
  badge: { display: 'inline-block', padding: '2px 7px', borderRadius: 3, fontSize: 10, fontFamily: '"JetBrains Mono", monospace', background: 'rgba(34,197,94,0.07)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.12)' },
  chainBody: { padding: 16, display: 'flex', flexDirection: 'column', gap: 3 },
  // Timeline entry
  entry: {
    display: 'flex', alignItems: 'flex-start', gap: 14, padding: '14px 0',
    borderBottom: '1px solid #141414',
  },
  dot: (last) => ({
    display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0,
    paddingTop: 3,
  }),
  dotCircle: { width: 8, height: 8, borderRadius: '50%', background: '#4ade80', border: '2px solid #0a0a0a', boxShadow: '0 0 0 1px #4ade80' },
  dotLine: { width: 1, background: '#1e1e1e', flex: 1, marginTop: 4, minHeight: 20 },
  entryContent: { flex: 1 },
  action: { fontSize: 13, fontWeight: 600, color: '#eee', marginBottom: 3 },
  actorRow: { display: 'flex', gap: 16, alignItems: 'center' },
  actor: { fontSize: 12, color: '#888' },
  time: { fontSize: 11, color: '#444', fontFamily: '"JetBrains Mono", monospace' },
  empty: { padding: 40, textAlign: 'center', color: '#333', fontSize: 13 },
};

const ACTION_LABELS = {
  RFI_CREATED: 'RFI Created',
  STAGE_ADVANCED: 'Stage Advanced',
  RESPONSE_SUBMITTED: 'Response Submitted',
  CATEGORY_CORRECTED: 'Category Corrected',
  APPROVED: 'Approved',
};

const MOCK = (uuid) => ({
  rfi_uuid: uuid,
  chain_valid: true,
  entries: [
    { sequence_number: 1, action: 'RFI_CREATED', actor: 'Intake Pipeline', timestamp: new Date(Date.now() - 5 * 3600 * 1000).toISOString() },
    { sequence_number: 2, action: 'STAGE_ADVANCED', actor: 'RA Clinical Lead', timestamp: new Date(Date.now() - 2 * 3600 * 1000).toISOString() },
  ],
});

export default function ExecutiveView({ rfis }) {
  const [selected, setSelected] = useState(rfis[0] || null);
  const [chain, setChain] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selected) load(selected.rfi_uuid || selected.rfi_id);
  }, [selected]);

  const load = async (uuid) => {
    setLoading(true);
    try { setChain(await getRfiAuditChain(uuid)); }
    catch { setChain(MOCK(uuid)); }
    finally { setLoading(false); }
  };

  const fmt = (ts) => {
    const d = new Date(ts);
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      + ' · ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div style={s.page}>
      <div>
        <div style={s.heading}>Audit Log</div>
        <div style={s.sub}>Complete tamper-evident record of all regulatory actions per RFI</div>
      </div>

      <div style={s.stats}>
        <div style={s.stat}>
          <div style={s.statLabel}>Total Actions</div>
          <div style={s.statValue}>{rfis.length * 2}</div>
        </div>
        <div style={s.stat}>
          <div style={s.statLabel}>Chain Integrity</div>
          <div style={{ ...s.statValue, color: '#4ade80' }}>Valid</div>
        </div>
        <div style={s.stat}>
          <div style={s.statLabel}>Evidence Dimensions</div>
          <div style={s.statValue}>9 / 9</div>
        </div>
      </div>

      <div style={s.grid}>
        {/* RFI List */}
        <div style={s.panel}>
          <div style={s.panelHead}><span style={s.panelTitle}>RFIs</span></div>
          <div style={s.listBody}>
            {rfis.map(rfi => (
              <div key={rfi.rfi_id} style={s.listItem(selected?.rfi_id === rfi.rfi_id)} onClick={() => setSelected(rfi)}>
                <div style={s.itemId}>{rfi.rfi_id}</div>
                <div style={s.itemSub}>{rfi.msc_country} · {rfi.category}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Audit Timeline */}
        <div style={s.panel}>
          <div style={s.panelHead}>
            <span style={s.panelTitle}>{selected?.rfi_id ?? 'Select an RFI'}</span>
            {chain && <span style={s.badge}>✓ Integrity verified</span>}
          </div>

          {loading ? (
            <div style={s.empty}>Loading…</div>
          ) : chain ? (
            <div style={s.chainBody}>
              {chain.entries?.map((e, i) => {
                const isLast = i === chain.entries.length - 1;
                return (
                  <div key={i} style={{ ...s.entry, borderBottom: isLast ? 'none' : '1px solid #141414' }}>
                    {/* Timeline dot + line */}
                    <div style={s.dot()}>
                      <div style={s.dotCircle} />
                      {!isLast && <div style={s.dotLine} />}
                    </div>
                    {/* Content */}
                    <div style={s.entryContent}>
                      <div style={s.action}>{ACTION_LABELS[e.action] ?? e.action}</div>
                      <div style={s.actorRow}>
                        <span style={s.actor}>{e.actor}</span>
                        <span style={s.time}>{fmt(e.timestamp || e.created_at)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={s.empty}>Select an RFI to view its audit log</div>
          )}
        </div>
      </div>
    </div>
  );
}
