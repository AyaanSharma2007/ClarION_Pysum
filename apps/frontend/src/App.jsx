import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import FilterBar from './components/FilterBar';
import RfiList from './components/RfiList';
import DetailPanel from './components/DetailPanel';
import { fetchAllRfis, parsePdfLayer1, ingestRfiLayer1 } from './services/api';

// ── CSS animation for slide-in panel
const styleEl = document.createElement('style');
styleEl.textContent = `
  @keyframes slideInRight {
    from { transform: translateX(40px); opacity: 0; }
    to   { transform: translateX(0);    opacity: 1; }
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }
`;
document.head.appendChild(styleEl);

const SORT_FNS = {
  sla_asc: (a, b) => {
    const ad = new Date(a.workflow_state?.sla_due_at || 0).getTime();
    const bd = new Date(b.workflow_state?.sla_due_at || 0).getTime();
    return ad - bd;
  },
  received_desc: (a, b) => new Date(b.received_at || 0) - new Date(a.received_at || 0),
  country_asc: (a, b) => (a.nca_country || '').localeCompare(b.nca_country || ''),
  risk_desc: (a, b) => (b._riskScore || 0) - (a._riskScore || 0),
};

const s = {
  root: {
    minHeight: '100vh',
    background: 'var(--bg)',
    display: 'flex',
    flexDirection: 'column',
  },
  topBar: {
    borderBottom: '1px solid var(--border)',
    padding: '0 28px',
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    height: 56,
    flexShrink: 0,
    position: 'sticky',
    top: 0,
    background: '#080808',
    zIndex: 50,
  },
  logo: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 15,
    fontWeight: 700,
    color: '#fff',
    letterSpacing: '-0.02em',
    flexShrink: 0,
  },
  logoSub: {
    fontSize: 10,
    fontWeight: 400,
    color: 'var(--text-dim)',
    display: 'block',
    letterSpacing: 0,
  },
  uploadBtn: (uploading) => ({
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '8px 16px',
    background: uploading ? '#1a1a1a' : '#fff',
    color: uploading ? '#888' : '#000',
    border: 'none',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 700,
    cursor: uploading ? 'not-allowed' : 'pointer',
    transition: 'all 0.15s',
    flexShrink: 0,
  }),
  refreshBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 7,
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '6px 11px',
    fontSize: 12,
    transition: 'border-color 0.15s',
    flexShrink: 0,
  },
  main: {
    flex: 1,
    maxWidth: 900,
    width: '100%',
    margin: '0 auto',
    padding: '0 28px 40px',
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
  },
  errorBanner: {
    margin: '16px 0',
    padding: '12px 16px',
    background: 'rgba(239,68,68,0.07)',
    border: '1px solid rgba(239,68,68,0.2)',
    borderRadius: 8,
    color: '#fca5a5',
    fontSize: 12,
  },
  loadingRow: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '80px 0',
    gap: 10,
    color: 'var(--text-dim)',
    fontSize: 13,
  },
};

export default function App() {
  const [rfis, setRfis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRfi, setSelectedRfi] = useState(null);
  const [pendingUploads, setPendingUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const [filters, setFilters] = useState({
    query: '',
    country: 'all',
    stage: 'all',
    category: 'all',
    sort: 'sla_asc',
  });

  // ── Fetch all RFIs ─────────────────────────────────────────────────────────
  const loadRfis = useCallback(async () => {
    try {
      const data = await fetchAllRfis();
      setRfis(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError('Could not reach Layer 2 (localhost:8001). Make sure the server is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRfis();
    const t = setInterval(loadRfis, 30000);
    return () => clearInterval(t);
  }, [loadRfis]);

  // ── Upload handler ─────────────────────────────────────────────────────────
  const handleFileSelected = useCallback(async (file) => {
    if (!file || uploading) return;
    if (!file.name.endsWith('.pdf') && file.type !== 'application/pdf') return;

    const pendingId = `pending-${Date.now()}`;
    const pendingEntry = { id: pendingId, filename: file.name };

    // 1. Optimistically show a faded placeholder row immediately
    setPendingUploads(prev => [...prev, pendingEntry]);
    setUploading(true);

    try {
      // 2. Parse PDF (runs against Layer 1 Ollama pipeline)
      const parsed = await parsePdfLayer1(file);

      // 3. Ingest into Layer 2
      await ingestRfiLayer1(parsed);

      // 4. Remove placeholder, refresh list to show real record
      setPendingUploads(prev => prev.filter(p => p.id !== pendingId));
      await loadRfis();
    } catch (e) {
      // Remove placeholder on failure (silently for non-IT users)
      setPendingUploads(prev => prev.filter(p => p.id !== pendingId));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [uploading, loadRfis]);

  // ── Distinct countries for filter dropdown ─────────────────────────────────
  const countries = useMemo(
    () => [...new Set(rfis.map(r => r.nca_country).filter(Boolean))].sort(),
    [rfis]
  );

  // ── Filtered + sorted list ─────────────────────────────────────────────────
  const displayRfis = useMemo(() => {
    let list = [...rfis];

    if (filters.query.trim()) {
      const q = filters.query.toLowerCase();
      list = list.filter(r =>
        r.rfi_id?.toLowerCase().includes(q) ||
        r.nca_country?.toLowerCase().includes(q) ||
        r.therapeutic_area_name?.toLowerCase().includes(q) ||
        r.category?.toLowerCase().includes(q) ||
        r.considerations?.some(c =>
          c.concern_text?.toLowerCase().includes(q) ||
          c.response_text?.toLowerCase().includes(q)
        )
      );
    }

    if (filters.country !== 'all') {
      list = list.filter(r => r.nca_country === filters.country);
    }

    if (filters.stage !== 'all') {
      list = list.filter(r =>
        (r.workflow_state?.current_stage || r.status) === filters.stage
      );
    }

    if (filters.category !== 'all') {
      list = list.filter(r => r.category === filters.category);
    }

    const sortFn = SORT_FNS[filters.sort] || SORT_FNS.sla_asc;
    list.sort(sortFn);

    return list;
  }, [rfis, filters]);

  return (
    <div style={s.root}>
      {/* ── Top Bar ── */}
      <header style={s.topBar}>
        <div style={s.logo}>
          ClarION
          <span style={s.logoSub}>EU CTR Regulatory Intelligence</span>
        </div>

        <button
          id="refresh-btn"
          style={s.refreshBtn}
          onClick={loadRfis}
          title="Refresh list"
          onMouseEnter={e => (e.target.style.borderColor = '#555')}
          onMouseLeave={e => (e.target.style.borderColor = 'var(--border)')}
        >
          ↻ Refresh
        </button>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          style={{ display: 'none' }}
          id="pdf-upload-input"
          onChange={e => handleFileSelected(e.target.files?.[0])}
        />

        <button
          id="upload-rfi-btn"
          style={s.uploadBtn(uploading)}
          disabled={uploading}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          {uploading ? '⏳ Processing…' : '↑ Upload RFI'}
        </button>
      </header>

      {/* ── Main Content ── */}
      <main style={s.main}>
        {error && <div style={s.errorBanner}>⚠ {error}</div>}

        {/* Filter Bar */}
        <FilterBar
          filters={filters}
          setFilters={setFilters}
          countries={countries}
          resultCount={displayRfis.length}
        />

        {/* RFI List */}
        {loading ? (
          <div style={s.loadingRow}>
            <span style={{ fontSize: 20, animation: 'spin 1s linear infinite', display: 'inline-block' }}>⏳</span>
            Loading RFIs from database…
          </div>
        ) : (
          <RfiList
            rfis={displayRfis}
            pendingUploads={pendingUploads}
            selectedId={selectedRfi?.id}
            onSelect={setSelectedRfi}
          />
        )}
      </main>

      {/* ── Detail Panel (slide-in) ── */}
      {selectedRfi && (
        <DetailPanel
          rfi={selectedRfi}
          onClose={() => setSelectedRfi(null)}
          onStageAdvanced={loadRfis}
        />
      )}
    </div>
  );
}
