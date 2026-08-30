import React, { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import {
  Database,
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Send,
  ArrowRight,
  RotateCcw,
  Layers,
  LayoutDashboard,
  ChevronDown,
  ChevronUp,
  Shield,
  Zap,
} from 'lucide-react'
import IngestionDashboard from './IngestionDashboard'

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
  const [activeTab, setActiveTab] = useState('intake')

  // Intake flow state
  const [step, setStep]               = useState(0)   // 0 upload, 1 review, 2 done
  const [uploading, setUploading]     = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [extracted, setExtracted]     = useState(null)
  const [filename, setFilename]       = useState('')
  const [forwarding, setForwarding]   = useState(false)
  const [forwardResult, setForwardResult] = useState(null)

  const handleFile = async (file) => {
    setUploading(true)
    setUploadError(null)
    setFilename(file.name)

    const form = new FormData()
    form.append('file', file)

    try {
      const res = await axios.post('http://localhost:8000/parse-pdf', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setExtracted(res.data)
      setStep(1)
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'PDF extraction failed. Check that the backend is running.'
      setUploadError(detail)
    } finally {
      setUploading(false)
    }
  }

  const handleForward = async () => {
    setForwarding(true)
    try {
      const res = await axios.post('http://localhost:8000/ingest', extracted)
      const data = res.data
      setForwardResult({
        ok: true,
        message: data.message || data.layer2_message || 'Record stored in Layer 2.',
        layer2Status: data.layer2_status,
      })
      setStep(2)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Forwarding failed.'
      setForwardResult({ ok: false, message: detail })
    } finally {
      setForwarding(false)
    }
  }

  const handleReset = () => {
    setStep(0)
    setExtracted(null)
    setFilename('')
    setUploadError(null)
    setForwardResult(null)
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* ── Header ── */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 sticky top-0 z-50">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 text-blue-400 rounded-xl border border-blue-500/30">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white leading-none">RFI Nexus</h1>
              <p className="text-[11px] text-slate-500 mt-0.5">EU CTR Validation Platform</p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              id="tab-intake"
              onClick={() => setActiveTab('intake')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'intake'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Intake
            </button>
            <button
              id="tab-dashboard"
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              Dashboard
            </button>
          </nav>

          <div className="hidden sm:flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Layer 1 Active
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-10">
        {activeTab === 'dashboard' ? (
          <IngestionDashboard />
        ) : (
          <>
            {/* Page title */}
            <div className="text-center mb-10">
              <h2 className="text-2xl font-bold text-white mb-2">RFI Document Intake</h2>
              <p className="text-sm text-slate-400 max-w-md mx-auto">
                Upload an EU CTR validation RFI PDF. Claude extracts the structured data,
                you review it, then it's forwarded to the Layer 2 central repository.
              </p>
            </div>

            <StepIndicator current={step === 2 ? 2 : step} />

            <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-8 backdrop-blur">
              {step === 0 && (
                <div className="space-y-4">
                  <DropZone onFile={handleFile} loading={uploading} />
                  {uploadError && (
                    <div className="flex items-start gap-3 px-4 py-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-sm">
                      <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      <span>{uploadError}</span>
                    </div>
                  )}
                </div>
              )}

              {(step === 1 || step === 2) && extracted && (
                <ReviewPanel
                  extracted={extracted}
                  filename={filename}
                  onConfirm={handleForward}
                  onReset={handleReset}
                  forwarding={forwarding}
                  forwardResult={forwardResult}
                />
              )}
            </div>

            {/* Flow footnote */}
            <div className="mt-6 flex items-center justify-center gap-6 text-xs text-slate-600">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500/60" />
                Layer 1 — Data Mesh Intake (port 8000)
              </span>
              <ArrowRight className="w-3 h-3" />
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-500/60" />
                Layer 2 — Central Repository (port 8001)
              </span>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
