import React, { useState, useEffect } from 'react';

function getSlaInfo(sla_due_at, rfi_type) {
  if (!sla_due_at) return { label: 'No SLA', color: 'var(--text-dim)', bg: '#f4f6fb', pct: 0 };
  const now = Date.now();
  const due = new Date(sla_due_at).getTime();
  const days = (rfi_type || '').toLowerCase() === 'assessment' ? 12 : 10;
  const totalMs = days * 24 * 60 * 60 * 1000;
  const diffMs = due - now;
  if (diffMs <= 0) return { label: 'Overdue', color: 'var(--red)', bg: 'var(--red-light)', pct: 0 };
  const hours = Math.floor(diffMs / 3600000);
  const mins = Math.floor((diffMs % 3600000) / 60000);
  const pct = Math.min(100, Math.round((diffMs / totalMs) * 100));
  const label = hours > 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h` : `${hours}h ${mins}m`;
  if (pct > 50) return { label, color: 'var(--green)', bg: 'var(--green-light)', pct };
  if (pct > 20) return { label, color: 'var(--amber)', bg: 'var(--amber-light)', pct };
  return { label, color: 'var(--red)', bg: 'var(--red-light)', pct };
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
    gap: 8,
    overflowY: 'auto',
    flex: 1,
    paddingTop: 4,
  },
  card: (selected) => ({
    background: selected ? 'var(--accent-blue-light)' : 'var(--bg-card)',
    border: `1.5px solid ${selected ? 'var(--accent-blue)' : 'var(--border)'}`,
    borderRadius: 'var(--radius-md)',
    padding: '14px 18px',
    cursor: 'pointer',
    transition: 'all 0.18s',
    display: 'flex',
    gap: 14,
    alignItems: 'center',
    boxShadow: selected ? '0 2px 12px rgba(79,114,255,0.14)' : 'var(--shadow-sm)',
  }),
  dot: (color) => ({
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: color,
    flexShrink: 0,
    boxShadow: `0 0 0 3px ${color}22`,
  }),
  main: { flex: 1, minWidth: 0 },
  topRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 5,
    flexWrap: 'wrap',
  },
  rfiId: {
    fontSize: 12,
    color: 'var(--text)',
    fontWeight: 600,
    flexShrink: 0,
    letterSpacing: '0.02em',
  },
  category: {
    fontSize: 10,
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: 20,
    background: 'var(--accent-pink-light)',
    color: 'var(--accent-pink)',
    flexShrink: 0,
  },
  indication: {
    fontSize: 12,
    color: 'var(--text-muted)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1,
  },
  bottomRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  country: {
    fontSize: 11,
    color: 'var(--text-dim)',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  stagePill: {
    fontSize: 10,
    padding: '2px 8px',
    borderRadius: 20,
    background: 'var(--accent-blue-light)',
    color: 'var(--accent-blue)',
    fontWeight: 500,
  },
  consCount: {
    fontSize: 11,
    color: 'var(--text-dim)',
  },
  slaRight: {
    textAlign: 'right',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: 4,
  },
  slaBadge: (color, bg) => ({
    fontSize: 11,
    fontWeight: 700,
    color,
    background: bg,
    padding: '3px 10px',
    borderRadius: 20,
    whiteSpace: 'nowrap',
  }),
  pendingRow: {
    background: 'var(--bg-card)',
    border: '1.5px dashed var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '14px 18px',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    opacity: 0.65,
  },
  pendingText: { fontSize: 12, color: 'var(--text-muted)' },
  pendingName: { fontSize: 12, color: 'var(--text)', fontWeight: 600 },
  empty: {
    padding: '64px 0',
    textAlign: 'center',
    color: 'var(--text-dim)',
    fontSize: 14,
    animation: 'fadeIn 0.3s ease',
  },
  emptyIcon: { fontSize: 36, marginBottom: 12 },
};

function SlaTimer({ sla_due_at, rfi_type }) {
  const [info, setInfo] = useState(() => getSlaInfo(sla_due_at, rfi_type));
  useEffect(() => {
    setInfo(getSlaInfo(sla_due_at, rfi_type));
    const t = setInterval(() => setInfo(getSlaInfo(sla_due_at, rfi_type)), 30000);
    return () => clearInterval(t);
  }, [sla_due_at, rfi_type]);

  return <div style={s.slaBadge(info.color, info.bg)}>{info.label}</div>;
}

export default function RfiList({ rfis, pendingUploads, selectedId, onSelect }) {
  if (rfis.length === 0 && pendingUploads.length === 0) {
    return (
      <div style={s.list}>
        <div style={s.empty}>
          <div style={s.emptyIcon}></div>
          No RFIs found. Upload a PDF to get started.
        </div>
      </div>
    );
  }

  return (
    <div style={s.list}>
      {pendingUploads.map(p => (
        <div key={p.id} style={s.pendingRow}>
          <div style={{ width: 18, height: 18, border: '2.5px solid var(--border)', borderTopColor: 'var(--accent-blue)', borderRadius: '50%', animation: 'spin 1s linear infinite', flexShrink: 0 }} />
          <div>
            <div style={s.pendingName}>{p.filename}</div>
            <div style={s.pendingText}>Parsing & ingesting — this may take a moment…</div>
          </div>
        </div>
      ))}

      {rfis.map(rfi => {
        const sla = getSlaInfo(rfi.workflow_state?.sla_due_at, rfi.rfi_type);
        const stage = rfi.workflow_state?.current_stage || rfi.status || 'received';
        const isSelected = rfi.id === selectedId;

        return (
          <div
            key={rfi.id}
            id={`rfi-row-${rfi.id}`}
            style={s.card(isSelected)}
            onClick={() => onSelect(rfi)}
            onMouseEnter={e => { if (!isSelected) { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.boxShadow = 'var(--shadow-md)'; e.currentTarget.style.borderColor = 'var(--border-hover)'; } }}
            onMouseLeave={e => { if (!isSelected) { e.currentTarget.style.background = 'var(--bg-card)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; e.currentTarget.style.borderColor = 'var(--border)'; } }}
          >
            <div style={s.dot(sla.color)} />

            <div style={s.main}>
              <div style={s.topRow}>
                <span style={s.rfiId}>{rfi.rfi_id}</span>
                {rfi.category && <span style={s.category}>{rfi.category}</span>}
                <span style={s.indication}>{rfi.therapeutic_area_name || '—'}</span>
              </div>
              <div style={s.bottomRow}>
                <span style={s.stagePill}>{STAGE_LABELS[stage] || stage}</span>
                {rfi.considerations?.length > 0 && (
                  <span style={s.consCount}>
                    {rfi.considerations.length} consideration{rfi.considerations.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>

            <div style={s.slaRight}>
              <SlaTimer sla_due_at={rfi.workflow_state?.sla_due_at} rfi_type={rfi.rfi_type} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
