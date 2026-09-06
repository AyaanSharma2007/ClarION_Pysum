import React, { useState, useEffect } from 'react';

function getSlaInfo(sla_due_at) {
  if (!sla_due_at) return { label: 'No SLA', color: 'var(--text-dim)', pct: 0 };
  const now = Date.now();
  const due = new Date(sla_due_at).getTime();
  const totalMs = 72 * 60 * 60 * 1000; // 72h standard window
  const diffMs = due - now;

  if (diffMs <= 0) return { label: 'OVERDUE', color: 'var(--red)', pct: 0 };

  const hours = Math.floor(diffMs / 3600000);
  const mins = Math.floor((diffMs % 3600000) / 60000);
  const pct = Math.min(100, Math.round((diffMs / totalMs) * 100));

  const label = hours > 24
    ? `${Math.floor(hours / 24)}d ${hours % 24}h`
    : `${hours}h ${mins}m`;

  const color = pct > 50 ? 'var(--green)' : pct > 20 ? 'var(--amber)' : 'var(--red)';
  return { label, color, pct };
}

const STAGE_LABELS = {
  received: 'Received',
  RA_Clinical_Review: 'RA Review',
  CTA_Mgmt_Review: 'CTA Review',
  EU_Hub_Approval: 'EU Approval',
  Submitted: 'Submitted',
};

const s = {
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    overflowY: 'auto',
    flex: 1,
  },
  card: (selected, faded) => ({
    background: selected ? '#1c1c1c' : '#111',
    border: `1px solid ${selected ? '#333' : 'var(--border)'}`,
    borderRadius: 10,
    padding: '14px 16px',
    cursor: faded ? 'default' : 'pointer',
    transition: 'background 0.15s, border-color 0.15s, transform 0.1s',
    opacity: faded ? 0.45 : 1,
    display: 'flex',
    gap: 14,
    alignItems: 'center',
  }),
  dot: (color) => ({
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: color,
    flexShrink: 0,
    boxShadow: `0 0 6px ${color}`,
  }),
  main: {
    flex: 1,
    minWidth: 0,
  },
  topRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  rfiId: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
    color: '#e5e5e5',
    fontWeight: 600,
    flexShrink: 0,
  },
  category: {
    fontSize: 10,
    fontWeight: 600,
    padding: '2px 6px',
    borderRadius: 4,
    background: 'rgba(59,130,246,0.1)',
    color: '#60a5fa',
    border: '1px solid rgba(59,130,246,0.2)',
    flexShrink: 0,
  },
  indication: {
    fontSize: 12,
    color: 'var(--text-muted)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  bottomRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginTop: 6,
  },
  country: {
    fontSize: 11,
    color: 'var(--text-dim)',
  },
  stagePill: {
    fontSize: 10,
    padding: '2px 7px',
    borderRadius: 4,
    background: '#1e1e1e',
    color: 'var(--text-dim)',
    border: '1px solid #2a2a2a',
  },
  slaRight: {
    marginLeft: 'auto',
    textAlign: 'right',
    flexShrink: 0,
  },
  slaLabel: (color) => ({
    fontSize: 12,
    fontWeight: 700,
    fontFamily: "'JetBrains Mono', monospace",
    color,
  }),
  slaBar: (pct, color) => ({
    height: 2,
    borderRadius: 1,
    background: `linear-gradient(to right, ${color} ${pct}%, #1e1e1e ${pct}%)`,
    width: 64,
    marginTop: 3,
  }),
  spinnerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '14px 16px',
    background: '#111',
    border: '1px dashed #2a2a2a',
    borderRadius: 10,
  },
  spinnerText: {
    fontSize: 12,
    color: 'var(--text-dim)',
  },
  empty: {
    padding: '60px 0',
    textAlign: 'center',
    color: 'var(--text-dim)',
    fontSize: 13,
  },
};

function SlaTimer({ sla_due_at }) {
  const [info, setInfo] = useState(() => getSlaInfo(sla_due_at));
  useEffect(() => {
    const t = setInterval(() => setInfo(getSlaInfo(sla_due_at)), 30000);
    return () => clearInterval(t);
  }, [sla_due_at]);

  return (
    <div style={s.slaRight}>
      <div style={s.slaLabel(info.color)}>{info.label}</div>
      <div style={s.slaBar(info.pct, info.color)} />
    </div>
  );
}

export default function RfiList({ rfis, pendingUploads, selectedId, onSelect }) {
  if (rfis.length === 0 && pendingUploads.length === 0) {
    return (
      <div style={s.list}>
        <div style={s.empty}>No RFIs found. Upload a PDF to get started.</div>
      </div>
    );
  }

  return (
    <div style={s.list}>
      {/* Pending uploads — faded optimistic rows */}
      {pendingUploads.map(p => (
        <div key={p.id} style={s.spinnerRow}>
          <span style={{ fontSize: 16, animation: 'spin 1s linear infinite' }}>⏳</span>
          <div>
            <div style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>{p.filename}</div>
            <div style={s.spinnerText}>Parsing & ingesting in background…</div>
          </div>
        </div>
      ))}

      {/* Real RFI rows */}
      {rfis.map(rfi => {
        const sla = getSlaInfo(rfi.workflow_state?.sla_due_at);
        const stage = rfi.workflow_state?.current_stage || rfi.status || 'received';
        const isSelected = rfi.id === selectedId;

        return (
          <div
            key={rfi.id}
            id={`rfi-row-${rfi.id}`}
            style={s.card(isSelected, false)}
            onClick={() => onSelect(rfi)}
            onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = '#161616'; }}
            onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = '#111'; }}
          >
            <div style={s.dot(sla.color)} />

            <div style={s.main}>
              <div style={s.topRow}>
                <span style={s.rfiId}>{rfi.rfi_id}</span>
                {rfi.category && <span style={s.category}>{rfi.category}</span>}
                <span style={{...s.indication, flex: 1}}>
                  {rfi.therapeutic_area_name || '—'}
                </span>
              </div>
              <div style={s.bottomRow}>
                <span style={s.country}>{rfi.nca_country || '—'}</span>
                <span style={s.stagePill}>{STAGE_LABELS[stage] || stage}</span>
                {rfi.considerations?.length > 0 && (
                  <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                    {rfi.considerations.length} consideration{rfi.considerations.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>

            <SlaTimer sla_due_at={rfi.workflow_state?.sla_due_at} />
          </div>
        );
      })}
    </div>
  );
}
