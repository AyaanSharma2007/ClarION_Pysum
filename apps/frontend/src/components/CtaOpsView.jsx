import React, { useState, useRef } from 'react';
import { parsePdfLayer1, ingestRfiLayer1 } from '../services/api';

//  Styles 
const s = {
  page: { 
    padding: '40px 0', 
    display: 'flex', 
    flexDirection: 'column', 
    gap: 32,
    alignItems: 'center',
    maxWidth: 800,
    margin: '0 auto'
  },
  
  // Massive dropzone/button
  dropzone: (dragOver) => ({
    width: '100%',
    padding: '80px 20px',
    border: `2px dashed ${dragOver ? '#4ade80' : '#333'}`,
    borderRadius: 24,
    background: dragOver ? 'rgba(74,222,128,0.05)' : '#111',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  }),
  dropIcon: { fontSize: 48, color: '#666' },
  dropLabel: { fontSize: 24, fontWeight: 700, color: '#fff' },
  
  // Parsed result boxes
  resultContainer: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
  },
  box: {
    background: '#111',
    border: '1px solid #222',
    borderRadius: 16,
    padding: '24px 32px',
  },
  boxLabel: {
    fontSize: 13,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    color: '#888',
    marginBottom: 12,
    fontWeight: 700
  },
  boxValue: {
    fontSize: 20,
    color: '#fff',
    lineHeight: 1.5,
    fontWeight: 500
  },
  
  // Action buttons
  ingestBtn: {
    width: '100%',
    padding: '24px',
    background: '#fff',
    color: '#000',
    border: 'none',
    borderRadius: 20,
    fontSize: 24,
    fontWeight: 800,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: '0 4px 24px rgba(255,255,255,0.1)'
  },
  ingestBtnDisabled: {
    width: '100%',
    padding: '24px',
    background: '#222',
    color: '#666',
    border: 'none',
    borderRadius: 20,
    fontSize: 24,
    fontWeight: 800,
    cursor: 'not-allowed'
  },
  
  // Status messages
  statusMsg: (type) => ({
    width: '100%',
    padding: '16px 20px',
    borderRadius: 12,
    background: type === 'ok' ? 'rgba(74,222,128,0.1)' : 'rgba(239,68,68,0.1)',
    color: type === 'ok' ? '#4ade80' : '#f87171',
    border: `1px solid ${type === 'ok' ? 'rgba(74,222,128,0.2)' : 'rgba(239,68,68,0.2)'}`,
    fontSize: 16,
    textAlign: 'center',
    fontWeight: 600
  })
};

//  Component 
export default function CtaOpsView() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [ingesting, setIngesting] = useState(false);

  // Data state
  const [parsedData, setParsedData] = useState(null);
  
  // Status
  const [status, setStatus] = useState(null); // { type: 'ok'|'err', msg: string }

  const fileInputRef = useRef(null);

  const handleFile = async (f) => {
    if (!f) return;
    setFile(f);
    setParsedData(null);
    setStatus(null);
    
    // Auto-parse on selection
    setParsing(true);
    setStatus({ type: 'ok', msg: 'Parsing PDF...' });
    try {
      const result = await parsePdfLayer1(f);
      setParsedData(result);
      setStatus(null); // Clear status on success to show ingest button cleanly
    } catch (err) {
      const detail = err.detail || err.message || JSON.stringify(err);
      setStatus({ type: 'err', msg: `Parse failed: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}` });
    } finally {
      setParsing(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault(); 
    setDragOver(false);
    handleFile(e.dataTransfer.files?.[0]);
  };

  const handleIngest = async () => {
    if (!parsedData || ingesting) return;
    setIngesting(true);
    setStatus({ type: 'ok', msg: 'Ingesting...' });
    
    try {
      await ingestRfiLayer1(parsedData);
      setStatus({ type: 'ok', msg: 'Successfully Ingested!' });
      // Reset after 3 seconds
      setTimeout(() => {
        setParsedData(null);
        setFile(null);
        setStatus(null);
      }, 3000);
    } catch (err) {
      const detail = err.detail || err.message || JSON.stringify(err);
      setStatus({ type: 'err', msg: `Ingest failed: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}` });
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div style={s.page}>

      {/* PDF Intake Button / Dropzone */}
      <div
        style={s.dropzone(dragOver)}
        onClick={() => !parsing && !ingesting && fileInputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <div style={s.dropIcon}>{parsing ? '' : ''}</div>
        <div style={s.dropLabel}>
          {parsing ? 'Extracting Data...' : (file ? file.name : 'PDF Intake')}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          style={{ display: 'none' }}
          onChange={e => handleFile(e.target.files?.[0])}
        />
      </div>

      {status && (
        <div style={s.statusMsg(status.type)}>{status.msg}</div>
      )}

      {/* Parsed Results (Big Boxes) */}
      {parsedData && (
        <div style={s.resultContainer}>
          <div style={s.box}>
            <div style={s.boxLabel}>RFI ID</div>
            <div style={s.boxValue}>{parsedData.rfi_id || '—'}</div>
          </div>
          
          <div style={s.box}>
            <div style={s.boxLabel}>Member State (Country)</div>
            <div style={s.boxValue}>{parsedData.msc?.country || '—'}</div>
          </div>

          <div style={s.box}>
            <div style={s.boxLabel}>Indication</div>
            <div style={s.boxValue}>{parsedData.indication?.name || '—'}</div>
          </div>

          {parsedData.considerations?.map((c, i) => (
            <React.Fragment key={i}>
              <div style={s.box}>
                <div style={s.boxLabel}>Concern Text {i + 1} {c.ctr_article?.name ? `(${c.ctr_article.name})` : ''}</div>
                <div style={{...s.boxValue, fontSize: 18}}>
                  {c.concern_text || 'No concern text provided.'}
                </div>
              </div>
              
              <div style={s.box}>
                <div style={s.boxLabel}>Sponsor Response {i + 1}</div>
                <div style={{...s.boxValue, fontSize: 18}}>
                  {c.response?.text || 'No response text provided.'}
                </div>
              </div>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Ingest Button */}
      {parsedData && (
        <button 
          style={ingesting ? s.ingestBtnDisabled : s.ingestBtn} 
          onClick={handleIngest}
          disabled={ingesting}
        >
          {ingesting ? 'Ingesting...' : 'Ingest'}
        </button>
      )}
    </div>
  );
}
