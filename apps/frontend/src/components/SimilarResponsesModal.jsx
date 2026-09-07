import React from 'react';

const s = {
  overlay: {
    position: 'fixed',
    top: 0, right: 0, bottom: 0, left: 0,
    background: 'rgba(10, 12, 20, 0.75)',
    backdropFilter: 'blur(8px)',
    zIndex: 200,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  modal: {
    background: 'var(--bg-sidebar)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    width: '100%',
    maxWidth: 800,
    maxHeight: '100%',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 24px 64px rgba(0,0,0,0.4)',
    animation: 'fadeIn 0.2s ease',
  },
  header: {
    padding: '24px 32px',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    color: 'var(--text)',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  closeBtn: {
    background: 'transparent',
    border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '7px 14px',
    fontSize: 13,
    transition: 'all 0.15s',
  },
  body: {
    padding: '32px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  card: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 24px',
    boxShadow: 'var(--shadow-sm)',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  rfiIdBadge: {
    display: 'inline-block',
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: '0.02em',
    color: 'var(--accent-blue)',
    background: 'var(--accent-blue-light)',
    padding: '4px 10px',
    borderRadius: 20,
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    color: 'var(--text-dim)',
    marginBottom: 6,
  },
  textBlock: {
    fontSize: 14,
    color: 'var(--text)',
    lineHeight: 1.65,
    background: 'var(--bg)',
    padding: '14px',
    borderRadius: 'var(--radius-sm)',
    borderLeft: '3px solid var(--border)',
  },
  concernBlock: {
    borderLeftColor: 'var(--accent-pink)',
  },
  responseBlock: {
    borderLeftColor: 'var(--accent-blue)',
  },
  notSubmitted: {
    fontSize: 14,
    color: 'var(--amber)',
    fontStyle: 'italic',
    padding: '14px',
    background: 'var(--amber-light)',
    borderRadius: 'var(--radius-sm)',
    borderLeft: '3px solid var(--amber)',
  },
};

export default function SimilarResponsesModal({ recommendations, onClose }) {
  return (
    <div style={s.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={s.modal}>
        <div style={s.header}>
          <div style={s.title}>
            <span></span> Similar Past Responses
          </div>
          <button
            style={s.closeBtn}
            onClick={onClose}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
             Close
          </button>
        </div>
        
        <div style={s.body}>
          {recommendations.map((rec, i) => (
            <div key={i} style={s.card}>
              <div>
                <span style={s.rfiIdBadge}>{rec.rfi_id || rec.consideration_id}</span>
              </div>
              
              <div>
                <div style={s.sectionTitle}>Concern Text</div>
                <div style={{ ...s.textBlock, ...s.concernBlock }}>
                  {rec.concern_text || 'No concern text available.'}
                </div>
              </div>
              
              <div>
                <div style={s.sectionTitle}>Submitted Response</div>
                {rec.response_text && rec.response_text.trim() !== '' ? (
                  <div style={{ ...s.textBlock, ...s.responseBlock }}>
                    {rec.response_text}
                  </div>
                ) : (
                  <div style={s.notSubmitted}>
                    RFI response not submitted
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
