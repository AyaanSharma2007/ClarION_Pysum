import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import FilterBar from './components/FilterBar';
import RfiList from './components/RfiList';
import DetailPanel from './components/DetailPanel';
import { fetchAllRfis, parsePdfLayer1, ingestRfiLayer1 } from './services/api';

// CSS animation for slide-in panel
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
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;
document.head.appendChild(styleEl);

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('clarion-theme') || 'light'; } catch { return 'light'; }
  });
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('clarion-theme', theme); } catch {}
  }, [theme]);
  const toggle = () => setTheme(t => t === 'light' ? 'dark' : 'light');
  return [theme, toggle];
}

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
    padding: '0 32px',
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    height: 62,
    flexShrink: 0,
    position: 'sticky',
    top: 0,
    background: 'var(--bg)',
    zIndex: 50,
    boxShadow: 'var(--shadow-sm)',
  },
  logoWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexShrink: 0,
  },
  logoIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    background: 'linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-pink) 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 16,
  },
  logo: {
    fontSize: 16,
    fontWeight: 700,
    color: 'var(--text)',
    letterSpacing: '-0.02em',
  },
  logoSub: {
    fontSize: 10,
    fontWeight: 400,
    color: 'var(--text-dim)',
    display: 'block',
    letterSpacing: 0,
  },
  refreshBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '7px 13px',
    fontSize: 12,
    transition: 'all 0.15s',
    flexShrink: 0,
  },
  uploadBtn: (uploading) => ({
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '9px 20px',
    background: uploading
      ? 'var(--bg)'
      : 'linear-gradient(135deg, var(--accent-blue) 0%, #6f8fff 100%)',
    color: uploading ? 'var(--text-muted)' : '#ffffff',
    border: uploading ? '1px solid var(--border)' : 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 13,
    fontWeight: 600,
    cursor: uploading ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s',
    flexShrink: 0,
    boxShadow: uploading ? 'none' : '0 2px 12px rgba(79,114,255,0.30)',
  }),
  main: {
    flex: 1,
    maxWidth: 920,
    width: '100%',
    margin: '0 auto',
    padding: '0 28px 48px',
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
  },
  errorBanner: {
    margin: '16px 0',
    padding: '12px 18px',
    background: 'var(--red-light)',
    border: '1px solid rgba(239,83,80,0.2)',
    borderRadius: 'var(--radius-sm)',
    color: '#c62828',
    fontSize: 13,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  loadingRow: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '80px 0',
    gap: 12,
    color: 'var(--text-dim)',
    fontSize: 14,
    animation: 'fadeIn 0.3s ease',
  },
};

export default function App() {
  const [theme, toggleTheme] = useTheme();
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
    date: '',
    trialId: '',
    euCtNumber: '',
    protocolCode: '',
    imp: '',
    therapeuticArea: '',
    rms: '',
    trialPhase: 'all',
    docType: '',
    proofOfPayment: '',
    protocol: '',
    icf: '',
  });

  const loadRfis = useCallback(async () => {
    try {
      const data = await fetchAllRfis();
      setRfis(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      console.error('[App] fetchAllRfis failed:', e);
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

  const handleFileSelected = useCallback(async (file) => {
    if (!file || uploading) return;
    if (!file.name.endsWith('.pdf') && file.type !== 'application/pdf') return;

    const pendingId = `pending-${Date.now()}`;
    setPendingUploads(prev => [...prev, { id: pendingId, filename: file.name }]);
    setUploading(true);

    try {
      const parsed = await parsePdfLayer1(file);
      await ingestRfiLayer1(parsed);
      setPendingUploads(prev => prev.filter(p => p.id !== pendingId));
      await loadRfis();
    } catch (e) {
      console.error('[App] PDF upload/ingest failed:', e);
      setPendingUploads(prev => prev.filter(p => p.id !== pendingId));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [uploading, loadRfis]);

  const countries = useMemo(
    () => [...new Set(rfis.map(r => r.nca_country).filter(Boolean))].sort(),
    [rfis]
  );

  const displayRfis = useMemo(() => {
    let list = [...rfis];

    // Text search query
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

    // Country
    if (filters.country !== 'all') list = list.filter(r => r.nca_country === filters.country);

    // Stage
    if (filters.stage !== 'all') list = list.filter(r => (r.workflow_state?.current_stage || r.status) === filters.stage);

    // Category
    if (filters.category !== 'all') list = list.filter(r => r.category === filters.category);

    // Date (submit_date, due_date, or response_date)
    if (filters.date) {
      list = list.filter(r =>
        (r.submit_date && r.submit_date.includes(filters.date)) ||
        (r.due_date && r.due_date.includes(filters.date)) ||
        (r.response_date && r.response_date.includes(filters.date))
      );
    }

    // Trial ID / EU-CT Number / Protocol Code
    if (filters.trialId?.trim()) {
      const q = filters.trialId.trim().toLowerCase();
      list = list.filter(r =>
        r.rfi_id?.toLowerCase().includes(q) ||
        r.source_document_ref?.toLowerCase().includes(q)
      );
    }

    if (filters.euCtNumber?.trim()) {
      const q = filters.euCtNumber.trim().toLowerCase();
      list = list.filter(r => r.rfi_id?.toLowerCase().includes(q));
    }

    if (filters.protocolCode?.trim()) {
      const q = filters.protocolCode.trim().toLowerCase();
      list = list.filter(r =>
        r.rfi_id?.toLowerCase().includes(q) ||
        r.considerations?.some(c => c.ctr_article_name?.toLowerCase().includes(q))
      );
    }

    // Investigational Medicinal Product (IMP)
    if (filters.imp?.trim()) {
      const q = filters.imp.trim().toLowerCase();
      list = list.filter(r =>
        r.rfi_text?.toLowerCase().includes(q) ||
        r.therapeutic_area_name?.toLowerCase().includes(q) ||
        r.considerations?.some(c => c.concern_text?.toLowerCase().includes(q))
      );
    }

    // Therapeutic Area
    if (filters.therapeuticArea?.trim()) {
      const q = filters.therapeuticArea.trim().toLowerCase();
      list = list.filter(r => r.therapeutic_area_name?.toLowerCase().includes(q));
    }

    // RMS (Ref Member State / NCA Country)
    if (filters.rms?.trim()) {
      const q = filters.rms.trim().toLowerCase();
      list = list.filter(r => r.nca_country?.toLowerCase().includes(q));
    }

    // Trial Phase
    if (filters.trialPhase && filters.trialPhase !== 'all') {
      const q = filters.trialPhase.toLowerCase();
      list = list.filter(r =>
        r.category?.toLowerCase().includes(q) ||
        r.rfi_text?.toLowerCase().includes(q) ||
        r.considerations?.some(c => c.concern_text?.toLowerCase().includes(q))
      );
    }

    // Document type requested
    if (filters.docType?.trim()) {
      const q = filters.docType.trim().toLowerCase();
      list = list.filter(r =>
        r.category?.toLowerCase().includes(q) ||
        r.considerations?.some(c =>
          c.ctr_article_name?.toLowerCase().includes(q) ||
          c.concern_text?.toLowerCase().includes(q)
        )
      );
    }

    // Proof of Payment
    if (filters.proofOfPayment?.trim()) {
      const q = filters.proofOfPayment.trim().toLowerCase();
      list = list.filter(r =>
        r.category?.toLowerCase().includes('payment') ||
        r.rfi_text?.toLowerCase().includes(q) ||
        r.considerations?.some(c => c.concern_text?.toLowerCase().includes(q) || c.ctr_article_name?.toLowerCase().includes(q))
      );
    }

    // Protocol
    if (filters.protocol?.trim()) {
      const q = filters.protocol.trim().toLowerCase();
      list = list.filter(r =>
        r.category?.toLowerCase().includes('protocol') ||
        r.considerations?.some(c =>
          c.ctr_article_name?.toLowerCase().includes(q) ||
          c.concern_text?.toLowerCase().includes(q)
        )
      );
    }

    // ICF (Informed Consent)
    if (filters.icf?.trim()) {
      const q = filters.icf.trim().toLowerCase();
      list = list.filter(r =>
        r.category?.toLowerCase().includes('consent') ||
        r.considerations?.some(c =>
          c.ctr_article_name?.toLowerCase().includes(q) ||
          c.concern_text?.toLowerCase().includes(q)
        )
      );
    }

    list.sort(SORT_FNS[filters.sort] || SORT_FNS.sla_asc);
    return list;
  }, [rfis, filters]);

  return (
    <div style={s.root}>
      {/* Top Bar */}
      <header style={s.topBar}>
        <div style={s.logoWrap}>
          <div>
            <div style={s.logo}>ClarION</div>
          </div>
        </div>

        <button
          id="theme-toggle-btn"
          style={s.refreshBtn}
          onClick={toggleTheme}
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
        </button>

        <button
          id="refresh-btn"
          style={s.refreshBtn}
          onClick={loadRfis}
          title="Refresh list"
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.borderColor = 'var(--border-hover)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--border)'; }}
        >
          ↻ Refresh
        </button>

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
          onMouseEnter={e => { if (!uploading) e.currentTarget.style.boxShadow = '0 4px 20px rgba(79,114,255,0.45)'; }}
          onMouseLeave={e => { if (!uploading) e.currentTarget.style.boxShadow = '0 2px 12px rgba(79,114,255,0.30)'; }}
        >
          {uploading ? '⏳ Processing…' : '↑  Upload RFI'}
        </button>
      </header>

      {/* Main Content */}
      <main style={s.main}>
        {error && (
          <div style={s.errorBanner}>
            <span>⚠</span> {error}
          </div>
        )}

        <FilterBar
          filters={filters}
          setFilters={setFilters}
          countries={countries}
          resultCount={displayRfis.length}
        />

        {loading ? (
          <div style={s.loadingRow}>
            <span style={{ fontSize: 22, animation: 'spin 1.2s linear infinite', display: 'inline-block' }}>⏳</span>
            Loading RFIs…
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
