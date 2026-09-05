import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import RaClinicalView from './components/RaClinicalView';
import CtaOpsView from './components/CtaOpsView';
import MedicalWritingView from './components/MedicalWritingView';
import RiskPredictorView from './components/RiskPredictorView';
import ExecutiveView from './components/ExecutiveView';
import GuidedDemoModal from './components/GuidedDemoModal';
import { checkSystemHealth } from './services/api';

const RFIS = [
  {
    rfi_uuid: 'CT-2026-QWEN-TEST-001',
    rfi_id: 'CT-2026-QWEN-TEST-001',
    msc_country: 'Denmark',
    indication_name: 'Immunology',
    category: 'IMPD Safety',
    stage: 'RA_Clinical_Review',
    sla_status: 'ACTIVE',
    due_date: new Date(Date.now() + 48 * 3600 * 1000).toISOString(),
    considerations: [{
      ctr_article: { name: 'Annex I, Section 63' },
      response: { text: 'IMPD Section 2.1 safety documentation and toxicological assay reporting updated.' },
    }],
  },
  {
    rfi_uuid: 'CT-2024-884920-14-DE-001',
    rfi_id: 'CT-2024-884920-14-DE-001',
    msc_country: 'Germany',
    indication_name: 'Type 2 Diabetes',
    category: 'Statistics',
    stage: 'Received',
    sla_status: 'ACTIVE',
    due_date: new Date(Date.now() + 30 * 3600 * 1000).toISOString(),
    considerations: [{
      ctr_article: { name: 'Part I – Regulatory / Annex I, Section 63' },
      response: { text: 'Statistical power calculation and sample size justification section 4.2 updated.' },
    }],
  },
  {
    rfi_uuid: 'CT-2024-991204-09-FR-002',
    rfi_id: 'CT-2024-991204-09-FR-002',
    msc_country: 'France',
    indication_name: 'Oncology',
    category: 'Protocol Design',
    stage: 'CTA_Mgmt_Review',
    sla_status: 'ACTIVE',
    due_date: new Date(Date.now() + 12 * 3600 * 1000).toISOString(),
    considerations: [{
      ctr_article: { name: 'Annex I, Section 12 – IMP Quality' },
      response: { text: 'Batch release specification and dosage regimen details updated.' },
    }],
  },
];

// ── Pipeline step indicator ────────────────────────────────────────────────────
const STEPS = ['Upload PDF', 'Review Extraction', 'Forward to Layer 2']

function StepIndicator({ current }) {
  return (
    <div className="flex items-center justify-center gap-0 mb-10">
      {STEPS.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <React.Fragment key={i}>
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                  done
                    ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/30'
                    : active
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30 ring-4 ring-blue-600/20'
                    : 'bg-slate-800 text-slate-500 border border-slate-700'
                }`}
              >
                {done ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
              </div>
              <span
                className={`text-[10px] font-medium whitespace-nowrap ${
                  active ? 'text-blue-400' : done ? 'text-emerald-400' : 'text-slate-500'
                }`}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`w-20 h-px mb-5 mx-1 transition-all duration-500 ${
                  i < current ? 'bg-emerald-500' : 'bg-slate-700'
                }`}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ── Drop zone ─────────────────────────────────────────────────────────────────
function DropZone({ onFile, loading }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (file) onFile(file)
    },
    [onFile]
  )

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !loading && inputRef.current?.click()}
      className={`relative group flex flex-col items-center justify-center gap-5 rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer select-none
        ${dragging
          ? 'border-blue-500 bg-blue-500/10 scale-[1.01]'
          : 'border-slate-700 bg-slate-900/40 hover:border-blue-500/60 hover:bg-blue-500/5'
        }
        ${loading ? 'pointer-events-none opacity-60' : ''}
        p-14`}
    >
      {/* Glow */}
      <div className={`absolute inset-0 rounded-2xl transition-opacity duration-300 ${dragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.08) 0%, transparent 70%)' }}
      />

      <div className={`p-5 rounded-2xl transition-all duration-300 ${dragging ? 'bg-blue-500/20 scale-110' : 'bg-slate-800 group-hover:bg-slate-700'}`}>
        {loading
          ? <Loader2 className="w-10 h-10 text-blue-400 animate-spin" />
          : <Upload className="w-10 h-10 text-slate-400 group-hover:text-blue-400 transition-colors" />
        }
      </div>

      <div className="text-center space-y-1.5">
        <p className="text-base font-semibold text-slate-200">
          {loading ? 'Extracting with Claude…' : 'Drop your RFI PDF here'}
        </p>
        <p className="text-sm text-slate-500">
          {loading ? 'Parsing document structure and entities' : 'or click to browse — PDF only'}
        </p>
      </div>

      {!loading && (
        <div className="flex items-center gap-4 text-xs text-slate-600">
          <span className="flex items-center gap-1.5"><Shield className="w-3 h-3" /> EU CTR validated</span>
          <span className="w-px h-3 bg-slate-700" />
          <span className="flex items-center gap-1.5"><Zap className="w-3 h-3" /> Claude-powered extraction</span>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f) }}
      />
    </div>
  )
}

// ── Consideration card (collapsible) ──────────────────────────────────────────
function ConsiderationCard({ c, index }) {
  const [open, setOpen] = useState(index === 0)
  return (
    <div className="rounded-xl border border-slate-800 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-900/60 hover:bg-slate-800/60 transition text-left"
      >
        <div className="flex items-center gap-3">
          <span className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-400 text-xs font-bold flex items-center justify-center border border-blue-500/30">
            {c.number}
          </span>
          <span className="text-sm font-medium text-slate-300 truncate max-w-xs">
            {c.ctr_article?.name || 'CTR Article'}
          </span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-500 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-4 py-4 space-y-3 bg-slate-950/40 border-t border-slate-800">
          {c.concern_text && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Concern</p>
              <p className="text-xs text-slate-300 leading-relaxed">{c.concern_text}</p>
            </div>
          )}
          {c.response?.text && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Sponsor Response</p>
              <p className="text-xs text-slate-300 leading-relaxed">{c.response.text}</p>
            </div>
          )}
          {c.outcome?.status && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Outcome</p>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {c.outcome.status}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Review panel ──────────────────────────────────────────────────────────────
function ReviewPanel({ extracted, filename, onConfirm, onReset, forwarding, forwardResult }) {
  const meta = [
    { label: 'RFI ID', value: extracted.rfi_id },
    { label: 'Member State', value: extracted.msc?.country },
    { label: 'Indication', value: extracted.indication?.name },
    { label: 'Due Date', value: extracted.due_date },
    { label: 'Response Date', value: extracted.response_date },
    { label: 'Submit Date', value: extracted.submit_date },
  ]

  return (
    <div className="space-y-6">
      {/* Source file badge */}
      <div className="flex items-center gap-3 px-4 py-3 bg-slate-900/50 border border-slate-800 rounded-xl">
        <FileText className="w-4 h-4 text-blue-400 flex-shrink-0" />
        <span className="text-sm text-slate-300 font-medium truncate">{filename}</span>
        <span className="ml-auto text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 flex-shrink-0">
          Extracted
        </span>
      </div>

      {/* Metadata grid */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">RFI Metadata</h3>
        <div className="grid grid-cols-2 gap-2">
          {meta.map(({ label, value }) => (
            <div key={label} className="bg-slate-900/60 border border-slate-800 rounded-xl px-4 py-3">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">{label}</p>
              <p className="text-sm font-medium text-slate-100 truncate">{value || '—'}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Considerations */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
          Considerations ({extracted.considerations?.length ?? 0})
        </h3>
        <div className="space-y-2">
          {(extracted.considerations ?? []).map((c, i) => (
            <ConsiderationCard key={i} c={c} index={i} />
          ))}
        </div>
      </div>

      {/* Actions / Result */}
      {forwardResult ? (
        <div className={`rounded-xl p-4 border ${
          forwardResult.ok
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
            : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
        }`}>
          <div className="flex items-center gap-2 font-medium text-sm mb-1">
            {forwardResult.ok
              ? <CheckCircle2 className="w-4 h-4" />
              : <AlertCircle className="w-4 h-4" />}
            {forwardResult.ok ? 'Successfully forwarded to Layer 2' : 'Forwarding failed'}
          </div>
          <p className="text-xs opacity-80">{forwardResult.message}</p>
          {forwardResult.ok && forwardResult.layer2Status && (
            <p className="text-xs mt-1 opacity-70">Layer 2: {forwardResult.layer2Status}</p>
          )}
          <button
            onClick={onReset}
            className="mt-3 flex items-center gap-2 text-xs font-medium opacity-70 hover:opacity-100 transition"
          >
            <RotateCcw className="w-3 h-3" /> Upload another PDF
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={onReset}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition px-4 py-2.5 rounded-xl border border-slate-800 hover:border-slate-600"
          >
            <RotateCcw className="w-4 h-4" />
            Re-upload
          </button>
          <button
            onClick={onConfirm}
            disabled={forwarding}
            className="flex-1 flex items-center justify-center gap-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition shadow-lg shadow-blue-600/20 cursor-pointer"
          >
            {forwarding
              ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Forwarding to Layer 2…</span></>
              : <><Send className="w-4 h-4" /><span>Forward to Layer 2</span><ArrowRight className="w-4 h-4" /></>
            }
          </button>
        </div>
      )}
    </div>
  )
}


// ── Main app ──────────────────────────────────────────────────────────────────
export default function App() {
  const [role, setRole] = useState('ra_clinical');
  const [health, setHealth] = useState({ layer1: false, layer2: false, ollama: false });
  const [showDemo, setShowDemo] = useState(false);

  useEffect(() => {
    const poll = async () => setHealth(await checkSystemHealth());
    poll();
    const t = setInterval(poll, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', display: 'flex', flexDirection: 'column' }}>
      <Header
        activeRole={role}
        setActiveRole={setRole}
        systemHealth={health}
        onOpenDemo={() => setShowDemo(true)}
      />

      <main style={{ flex: 1, maxWidth: 1280, width: '100%', margin: '0 auto', padding: '0 24px' }}>
        {role === 'ra_clinical'     && <RaClinicalView rfis={RFIS} onRefresh={() => {}} />}
        {role === 'cta_ops'         && <CtaOpsView onRefresh={() => {}} />}
        {role === 'risk_engine'     && <RiskPredictorView />}
        {role === 'medical_writing' && <MedicalWritingView />}
        {role === 'executive'       && <ExecutiveView rfis={RFIS} />}
      </main>

      {showDemo && (
        <GuidedDemoModal onClose={() => setShowDemo(false)} setActiveRole={setRole} />
      )}
    </div>
  );
}
