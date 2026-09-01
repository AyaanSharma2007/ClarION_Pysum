import React from 'react';

const S = {
  header: {
    background: '#0a0a0a',
    borderBottom: '1px solid #1e1e1e',
    position: 'sticky',
    top: 0,
    zIndex: 50,
    padding: '0 24px',
  },
  inner: {
    maxWidth: 1280,
    margin: '0 auto',
    height: 52,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 24,
  },
  brand: {
    fontFamily: '"JetBrains Mono", monospace',
    fontWeight: 700,
    fontSize: 15,
    color: '#fff',
    letterSpacing: '-0.02em',
    whiteSpace: 'nowrap',
  },
  nav: { display: 'flex', alignItems: 'center', gap: 2 },
  tab: (active) => ({
    padding: '5px 14px',
    borderRadius: 6,
    border: 'none',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 500,
    transition: 'all 0.15s',
    background: active ? '#fff' : 'transparent',
    color: active ? '#000' : '#666',
    fontFamily: 'inherit',
  }),
  right: { display: 'flex', alignItems: 'center', gap: 14 },
  status: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    fontSize: 11,
    fontFamily: '"JetBrains Mono", monospace',
    color: '#555',
  },
  dot: (on) => ({
    display: 'inline-block',
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: on ? '#22c55e' : '#333',
    marginRight: 4,
  }),
  demoBtn: {
    background: 'transparent',
    border: '1px solid #2a2a2a',
    color: '#777',
    borderRadius: 6,
    padding: '5px 12px',
    fontSize: 11,
    cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'all 0.15s',
  },
};

const TABS = [
  { id: 'ra_clinical',     label: 'Clinical Queue' },
  { id: 'cta_ops',         label: 'Intake' },
  { id: 'medical_writing', label: 'Search' },
  { id: 'executive',       label: 'Audit' },
];

export default function Header({ activeRole, setActiveRole, systemHealth, onOpenDemo }) {
  return (
    <header style={S.header}>
      <div style={S.inner}>
        <span style={S.brand}>ClarION</span>

        <nav style={S.nav}>
          {TABS.map(t => (
            <button key={t.id} style={S.tab(activeRole === t.id)} onClick={() => setActiveRole(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>

        <div style={S.right}>
          <div style={S.status}>
            <span><span style={S.dot(systemHealth.layer1)} />API</span>
            <span><span style={S.dot(systemHealth.layer2)} />Repo</span>
            <span><span style={S.dot(systemHealth.ollama)} />AI</span>
          </div>
          <button style={S.demoBtn} onClick={onOpenDemo}>Demo</button>
        </div>
      </div>
    </header>
  );
}
