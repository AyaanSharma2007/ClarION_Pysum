import React, { useState, useRef } from 'react';
import { parsePdfLayer1, ingestRfiLayer1 } from '../services/api';

// ─── Safety Gateway patterns mirrored from backend/app/safety_gateway.py ──────
// Used to run a client-side pre-screen before hitting the API, matching exactly
// what the server checks (Bible §6.2 deterministic heuristic boundary).
const INJECTION_PATTERNS = [
  /ignore (all )?(previous|prior|above) instructions/i,
  /disregard (the )?system prompt/i,
  /you are now/i,
  /act as (an?|the) (?!regulatory)/i,
  /reveal (your|the) (system|hidden) prompt/i,
];

function runSafetyGateway(jsonText) {
  const hits = INJECTION_PATTERNS.filter(p => p.test(jsonText));
  return { flagged: hits.length > 0, count: hits.length };
}

// ─── Default sample payload matching RFIExtractionTemplate schema ─────────────
const DEFAULT_PAYLOAD = {
  rfi_id: 'CT-2024-123456-12-00-SM01-001',
  due_date: '2026-03-16',
  response_date: '2026-03-06',
  submit_date: '2026-03-05',
  msc: { country: 'Germany' },
  indication: { name: 'Type 2 Diabetes Mellitus' },
  considerations: [
    {
      number: 1,
      ctr_article: { name: 'Part I - Regulatory / Annex I, Section 63' },
      response: { text: 'Proof of payment of the additional amount required is provided.' },
      outcome: null,
    },
  ],
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = {
  page: { padding: '28px 0', display: 'flex', flexDirection: 'column', gap: 20 },
  heading: { fontSize: 16, fontWeight: 600, color: '#fff', marginBottom: 3 },
  sub: { fontSize: 12, color: '#555' },

  // Two-column layout
  cols: { display: 'grid', gridTemplateColumns: '340px 1fr', gap: 14, alignItems: 'start' },

  // Generic panel
  panel: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 8, overflow: 'hidden' },
  panelHead: { padding: '12px 16px', borderBottom: '1px solid #1e1e1e', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  panelTitle: { fontSize: 13, fontWeight: 600, color: '#fff' },
  panelBody: { padding: 16, display: 'flex', flexDirection: 'column', gap: 14 },

  // Upload area
  dropzone: (dragOver) => ({
    border: `1px dashed ${dragOver ? '#555' : '#2a2a2a'}`,
    borderRadius: 7,
    padding: '24px 16px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'border-color 0.15s, background 0.15s',
    background: dragOver ? '#161616' : 'transparent',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 6,
  }),
  dropIcon: { fontSize: 22, color: '#444' },
  dropLabel: { fontSize: 12, color: '#555' },
  fileName: { fontSize: 11, color: '#888', fontFamily: '"JetBrains Mono", monospace', wordBreak: 'break-all', marginTop: 2 },
  fileSize: { fontSize: 10, color: '#444', fontFamily: '"JetBrains Mono", monospace' },

  // Buttons
  btn: (disabled) => ({
    padding: '9px 0',
    background: disabled ? '#1a1a1a' : '#fff',
    color: disabled ? '#444' : '#000',
    border: 'none',
    borderRadius: 7,
    fontSize: 13,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    width: '100%',
    transition: 'all 0.15s',
    fontFamily: 'inherit',
  }),
  ghostBtn: {
    background: 'transparent',
    border: 'none',
    color: '#555',
    fontSize: 11,
    cursor: 'pointer',
    padding: '3px 0',
    fontFamily: 'inherit',
    transition: 'color 0.1s',
  },

  // Safety Gateway callout
  gatewayOk: {
    padding: '10px 12px',
    background: 'rgba(34,197,94,0.05)',
    border: '1px solid rgba(34,197,94,0.12)',
    borderRadius: 7,
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
  },
  gatewayFlagged: {
    padding: '10px 12px',
    background: 'rgba(239,68,68,0.06)',
    border: '1px solid rgba(239,68,68,0.18)',
    borderRadius: 7,
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
  },
  gatewayDot: (ok) => ({
    width: 7, height: 7, borderRadius: '50%', flexShrink: 0, marginTop: 3,
    background: ok ? '#4ade80' : '#f87171',
  }),
  gatewayTitle: (ok) => ({ fontSize: 12, fontWeight: 600, color: ok ? '#4ade80' : '#f87171', marginBottom: 2 }),
  gatewayDesc: { fontSize: 11, color: '#666', lineHeight: 1.55 },

  // JSON editor
  textarea: {
    width: '100%',
    background: '#000',
    border: '1px solid #1e1e1e',
    borderRadius: 7,
    padding: '12px 14px',
    color: '#ccc',
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: 11.5,
    lineHeight: 1.65,
    resize: 'vertical',
    outline: 'none',
    minHeight: 340,
    transition: 'border-color 0.15s',
    boxSizing: 'border-box',
  },

  // Status messages
  alert: (type) => ({
    padding: '10px 14px',
    borderRadius: 7,
    border: `1px solid ${type === 'ok' ? 'rgba(74,222,128,0.18)' : type === 'warn' ? 'rgba(251,191,36,0.18)' : 'rgba(248,113,113,0.18)'}`,
    background: type === 'ok' ? 'rgba(34,197,94,0.04)' : type === 'warn' ? 'rgba(245,158,11,0.04)' : 'rgba(239,68,68,0.04)',
    color: type === 'ok' ? '#4ade80' : type === 'warn' ? '#fbbf24' : '#f87171',
    fontSize: 12,
    lineHeight: 1.55,
    fontFamily: '"JetBrains Mono", monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  }),

  // Result panel
  resultBox: { background: '#0a0a0a', border: '1px solid #1a1a1a', borderRadius: 7, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6 },
  resultRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  resultKey: { fontSize: 11, color: '#555', textTransform: 'uppercase', letterSpacing: '0.06em' },
  resultVal: (ok) => ({ fontSize: 12, fontFamily: '"JetBrains Mono", monospace', color: ok ? '#4ade80' : '#f87171', fontWeight: 500 }),

  divider: { height: 1, background: '#1a1a1a' },
  schema: {
    padding: '10px 12px',
    background: '#0a0a0a',
    border: '1px solid #1a1a1a',
    borderRadius: 6,
    fontSize: 10.5,
    color: '#555',
    fontFamily: '"JetBrains Mono", monospace',
    lineHeight: 1.6,
  },
};

// ─── Component ────────────────────────────────────────────────────────────────
export default function CtaOpsView() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [ingesting, setIngesting] = useState(false);

  // Editor state
  const [jsonText, setJsonText] = useState(JSON.stringify(DEFAULT_PAYLOAD, null, 2));

  // Gateway state — computed live from jsonText
  const gateway = runSafetyGateway(jsonText);

  // Status for parse + ingest
  const [parseStatus, setParseStatus] = useState(null);   // {type, msg}
  const [ingestResult, setIngestResult] = useState(null); // full response object
  const [ingestError, setIngestError] = useState(null);

  const fileInputRef = useRef(null);

  // ── File handling ──────────────────────────────────────────────────────────
  const handleFile = (f) => {
    if (!f) return;
    if (!f.name.endsWith('.pdf') && f.type !== 'application/pdf') {
      setParseStatus({ type: 'err', msg: 'Only .pdf files are accepted.' });
      return;
    }
    setFile(f);
    setParseStatus(null);
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    handleFile(e.dataTransfer.files?.[0]);
  };

  // ── Parse PDF ──────────────────────────────────────────────────────────────
  const handleParse = async () => {
    if (!file || parsing) return;
    setParsing(true); setParseStatus(null); setIngestResult(null); setIngestError(null);
    try {
      const result = await parsePdfLayer1(file);
      setJsonText(JSON.stringify(result, null, 2));
      setParseStatus({ type: 'ok', msg: `Parsed successfully. Payload loaded into editor.` });
    } catch (err) {
      const detail = err.detail || err.message || JSON.stringify(err);
      setParseStatus({ type: 'err', msg: `Parse failed: ${detail}` });
    } finally {
      setParsing(false);
    }
  };

  // ── Ingest ─────────────────────────────────────────────────────────────────
  const handleIngest = async () => {
    if (ingesting) return;
    setIngestResult(null); setIngestError(null);

    // Parse JSON
    let payload;
    try {
      payload = JSON.parse(jsonText);
    } catch {
      setIngestError('JSON syntax error — fix the editor before submitting.');
      return;
    }

    setIngesting(true);
    try {
      const res = await ingestRfiLayer1(payload);
      setIngestResult(res);
    } catch (err) {
      const detail = err.detail || err.message || JSON.stringify(err);
      setIngestError(typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2));
    } finally {
      setIngesting(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      <div>
        <div style={s.heading}>Intake Portal</div>
        <div style={s.sub}>Upload an RFI document or edit the payload directly, then submit to Layer 1 for validation and forwarding</div>
      </div>

      <div style={s.cols}>

        {/* ── Left: PDF Upload + Safety Gateway ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Upload panel */}
          <div style={s.panel}>
            <div style={s.panelHead}>
              <span style={s.panelTitle}>PDF Document Parser</span>
            </div>
            <div style={s.panelBody}>

              {/* Dropzone */}
              <div
                style={s.dropzone(dragOver)}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
              >
                <div style={s.dropIcon}>↑</div>
                <div style={s.dropLabel}>
                  {file ? 'Click to change file' : 'Click or drag to upload a PDF'}
                </div>
                {file && (
                  <>
                    <div style={s.fileName}>{file.name}</div>
                    <div style={s.fileSize}>{(file.size / 1024).toFixed(1)} KB</div>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  style={{ display: 'none' }}
                  onChange={e => handleFile(e.target.files?.[0])}
                />
              </div>

              {/* Parse button */}
              <button
                style={s.btn(!file || parsing)}
                disabled={!file || parsing}
                onClick={handleParse}
              >
                {parsing ? 'Extracting…' : 'Extract from PDF'}
              </button>

              {/* Parse status */}
              {parseStatus && (
                <div style={s.alert(parseStatus.type === 'ok' ? 'ok' : 'err')}>
                  {parseStatus.msg}
                </div>
              )}

              <div style={s.divider} />

              {/* Schema reference */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 10, color: '#444', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  Expected Schema (RFIExtractionTemplate)
                </div>
                <div style={s.schema}>
{`rfi_id         string  (required)
due_date       YYYY-MM-DD
response_date  YYYY-MM-DD
submit_date    YYYY-MM-DD
msc.country    string  (required)
indication.name  string  (required)
considerations[]
  .number        int
  .ctr_article.name  string
  .response.text     string
  .outcome       null | {status}`}
                </div>
              </div>
            </div>
          </div>

          {/* ── Safety Gateway Callout (Bible §6.2) ── */}
          <div style={s.panel}>
            <div style={s.panelHead}>
              <span style={s.panelTitle}>Input Screening</span>
              <span style={{
                fontSize: 10, fontFamily: '"JetBrains Mono", monospace',
                color: gateway.flagged ? '#f87171' : '#4ade80',
              }}>
                {gateway.flagged ? '● FLAGGED' : '● CLEAR'}
              </span>
            </div>
            <div style={s.panelBody}>
              <div style={gateway.flagged ? s.gatewayFlagged : s.gatewayOk}>
                <div style={s.gatewayDot(!gateway.flagged)} />
                <div>
                  <div style={s.gatewayTitle(!gateway.flagged)}>
                    {gateway.flagged ? 'Potential prompt injection detected' : 'No injection patterns found'}
                  </div>
                  <div style={s.gatewayDesc}>
                    {gateway.flagged
                      ? `${gateway.count} suspicious pattern(s) matched in the payload. The backend will quarantine this text before forwarding to the AI model.`
                      : 'All response text passes deterministic boundary checks. Safe to forward to the extraction pipeline.'
                    }
                  </div>
                </div>
              </div>

              <div style={{ fontSize: 11, color: '#444', lineHeight: 1.55 }}>
                The intake pipeline runs 5 regex rules against all sponsor response text before it reaches any AI model. Flagged payloads are logged for review but still accepted into the system.
              </div>
            </div>
          </div>
        </div>

        {/* ── Right: JSON Editor + Ingest ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          <div style={s.panel}>
            <div style={s.panelHead}>
              <span style={s.panelTitle}>Payload Editor</span>
              <button
                style={s.ghostBtn}
                onClick={() => {
                  setJsonText(JSON.stringify(DEFAULT_PAYLOAD, null, 2));
                  setIngestResult(null); setIngestError(null); setParseStatus(null);
                }}
              >
                Reset to sample
              </button>
            </div>
            <div style={s.panelBody}>

              {/* JSON textarea */}
              <textarea
                style={{
                  ...s.textarea,
                  borderColor: ingestError ? 'rgba(248,113,113,0.25)' : '#1e1e1e',
                }}
                value={jsonText}
                onChange={e => {
                  setJsonText(e.target.value);
                  setIngestError(null);
                  setIngestResult(null);
                }}
                spellCheck={false}
              />

              {/* JSON parse error / ingest error */}
              {ingestError && (
                <div style={s.alert('err')}>{ingestError}</div>
              )}

              {/* Ingest button */}
              <button
                style={s.btn(ingesting)}
                disabled={ingesting}
                onClick={handleIngest}
              >
                {ingesting ? 'Validating & Submitting…' : 'Submit to Layer 1'}
              </button>

              {/* ── Ingest Result Diagnostics ── */}
              {ingestResult && (
                <div style={s.resultBox}>
                  <div style={s.resultRow}>
                    <span style={s.resultKey}>Status</span>
                    <span style={s.resultVal(ingestResult.status === 'success')}>
                      {ingestResult.status?.toUpperCase()}
                    </span>
                  </div>
                  <div style={s.divider} />
                  <div style={s.resultRow}>
                    <span style={s.resultKey}>Validation</span>
                    <span style={s.resultVal(ingestResult.db_status?.includes('persisted'))}>
                      {ingestResult.db_status}
                    </span>
                  </div>
                  <div style={s.resultRow}>
                    <span style={s.resultKey}>Layer 2 Forward</span>
                    <span style={s.resultVal(
                      ingestResult.layer2_status === 'forwarded' || ingestResult.layer2_status === 'duplicate'
                    )}>
                      {ingestResult.layer2_status}
                    </span>
                  </div>
                  {ingestResult.layer2_message && (
                    <div style={{ fontSize: 11, color: '#555', marginTop: 2 }}>
                      {ingestResult.layer2_message}
                    </div>
                  )}
                  {ingestResult.record?.ingested_at && (
                    <>
                      <div style={s.divider} />
                      <div style={s.resultRow}>
                        <span style={s.resultKey}>Ingested At</span>
                        <span style={{ fontSize: 11, fontFamily: '"JetBrains Mono", monospace', color: '#666' }}>
                          {new Date(ingestResult.record.ingested_at).toLocaleString()}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )}

            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
