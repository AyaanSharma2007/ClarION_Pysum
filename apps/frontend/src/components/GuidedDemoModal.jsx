import React, { useState } from 'react';

const STEPS = [
  {
    id: 1, role: 'cta_ops',
    title: 'Phase 1 — Capture & Parse',
    desc: 'PDF intake & Safety Gateway pre-filtering. Accepts official EU CTR PDF documents, validates structural schema, and extracts consideration text block by block.',
  },
  {
    id: 2, role: 'cta_ops',
    title: 'Phase 2 — Connect & Classify',
    desc: 'Local Qwen 2.5 LLM category tagging. Classifies considerations into regulatory categories (IMPD Safety, Statistics, Protocol) on-device with zero cloud data exposure.',
  },
  {
    id: 3, role: 'medical_writing',
    title: 'Phase 3 — Predict & Recommend',
    desc: 'Dual pgvector semantic search + Neo4j structural graph context. Queries historical precedent responses, Louvain community clusters, and graph centrality scores.',
  },
  {
    id: 4, role: 'ra_clinical',
    title: 'Phase 4 — Submission Gate',
    desc: 'Statutory SLA timer & human stage advancement. Enforces the strict 72-hour regulatory SLA countdown and requires explicit human sign-off before workflow advancement.',
  },
  {
    id: 5, role: 'executive',
    title: 'Phase 5 — Govern & Audit',
    desc: 'Cryptographic SHA-256 hash chain verification. Computes prev_hash and curr_hash for every action across all workflow stages to ensure 100% tamper-evident GxP compliance.',
  },
];

const s = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 100,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    backdropFilter: 'blur(2px)',
  },
  modal: {
    background: '#111', border: '1px solid #2a2a2a', borderRadius: 12,
    width: 540, maxWidth: '90vw', padding: 32, display: 'flex', flexDirection: 'column', gap: 24,
  },
  topRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  step: { fontSize: 11, color: '#555', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 },
  title: { fontSize: 18, fontWeight: 700, color: '#fff', lineHeight: 1.3 },
  desc: { fontSize: 14, color: '#888', lineHeight: 1.7 },
  progress: { display: 'flex', gap: 6 },
  pip: (a) => ({ height: 3, flex: 1, borderRadius: 2, background: a ? '#fff' : '#222', transition: 'background 0.2s' }),
  actions: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 },
  closeBtn: { background: 'transparent', border: '1px solid #2a2a2a', color: '#666', borderRadius: 6, padding: '7px 14px', fontSize: 12, cursor: 'pointer' },
  backBtn: { background: 'transparent', border: '1px solid #2a2a2a', color: '#666', borderRadius: 6, padding: '7px 14px', fontSize: 12, cursor: 'pointer' },
  nextBtn: { background: '#fff', border: 'none', color: '#000', borderRadius: 6, padding: '8px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer' },
  label: { fontSize: 11, color: '#555' },
};

export default function GuidedDemoModal({ onClose, setActiveRole }) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  const goNext = () => {
    if (step < STEPS.length - 1) {
      const next = STEPS[step + 1];
      setStep(step + 1);
      setActiveRole(next.role);
    } else {
      onClose();
    }
  };

  const goBack = () => {
    if (step > 0) {
      setStep(step - 1);
      setActiveRole(STEPS[step - 1].role);
    }
  };

  // Set role when demo opens
  React.useEffect(() => {
    setActiveRole(current.role);
  }, []);

  return (
    <div style={s.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={s.modal}>
        <div style={s.topRow}>
          <div>
            <div style={s.step}>Guided Demo · {step + 1} of {STEPS.length}</div>
            <div style={s.title}>{current.title}</div>
          </div>
          <button style={s.closeBtn} onClick={onClose}></button>
        </div>

        {/* Progress */}
        <div style={s.progress}>
          {STEPS.map((_, i) => <div key={i} style={s.pip(i <= step)} />)}
        </div>

        <div style={s.desc}>{current.desc}</div>

        <div style={s.actions}>
          <button style={s.backBtn} onClick={goBack} disabled={step === 0}>← Back</button>
          <span style={s.label}>Now viewing: <strong style={{ color: '#ddd' }}>{current.role.replace(/_/g, ' ')}</strong></span>
          <button style={s.nextBtn} onClick={goNext}>
            {step === STEPS.length - 1 ? 'Finish' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  );
}
