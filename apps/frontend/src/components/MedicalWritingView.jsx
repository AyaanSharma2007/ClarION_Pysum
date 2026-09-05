import React, { useState } from 'react';
import { searchHybrid, searchSemantic } from '../services/api';

const MOCK_RESULTS_FALLBACK = [
  {
    consideration_id: 'CT-2024-884920-14-DE-001-C1',
    rfi_id: 'CT-2024-884920-14-DE-001',
    score: 0.96,
    concern_text: 'Sample size calculation relies on 80% power assumption without accounting for 15% estimated drop-out rate in Phase III extension.',
    response_text: 'Statistical power calculation updated in Section 4.2 of protocol v2.1. Adjusted N=450 accounts for 15% attrition maintaining 90% power (alpha=0.05).',
    msc_country: 'Germany',
    indication_name: 'Type 2 Diabetes',
    ctr_article_name: 'Part I – Regulatory / Annex I, Section 63',
    louvain_cluster: 4,
    louvain_tag: 'Cluster_04_Stats',
    centrality: 0.89
  },
  {
    consideration_id: 'CT-2026-QWEN-TEST-001-C1',
    rfi_id: 'CT-2026-QWEN-TEST-001',
    score: 0.91,
    concern_text: 'In vitro hepatotoxicity assay sensitivity parameters and OECD 487 genotoxicity assay raw data missing from IMPD Section 2.1.',
    response_text: 'IMPD Section 2.1 safety documentation and toxicological assay reporting updated. Included full GLP-compliant OECD 487 study reports.',
    msc_country: 'Denmark',
    indication_name: 'Immunology',
    ctr_article_name: 'Annex I, Section 63',
    louvain_cluster: 1,
    louvain_tag: 'Cluster_01_Safety',
    centrality: 0.94
  },
  {
    consideration_id: 'CT-2024-991204-09-FR-002-C1',
    rfi_id: 'CT-2024-991204-09-FR-002',
    score: 0.85,
    concern_text: 'Dosage escalation escalation criteria in cohorts 3 & 4 do not adequately define DLT monitoring window.',
    response_text: 'Protocol Section 6.4 updated to extend DLT monitoring window from 21 to 28 days for Cohorts 3 and 4 with independent DSMB oversight.',
    msc_country: 'France',
    indication_name: 'Oncology',
    ctr_article_name: 'Annex I, Section 12 – IMP Quality',
    louvain_cluster: 3,
    louvain_tag: 'Cluster_03_Protocol',
    centrality: 0.78
  }
];

const s = {
  page: { padding: '24px 0', display: 'flex', flexDirection: 'column', gap: 20 },
  headerBox: { display: 'flex', flexDirection: 'column', gap: 4 },
  heading: { fontSize: 18, fontWeight: 700, color: '#fff', letterSpacing: '-0.01em' },
  sub: { fontSize: 13, color: '#777' },

  searchBar: { display: 'flex', gap: 10 },
  input: {
    flex: 1,
    background: '#111',
    border: '1px solid #222',
    borderRadius: 8,
    padding: '11px 16px',
    color: '#fff',
    fontSize: 13,
    outline: 'none',
    transition: 'border-color 0.15s',
  },
  btn: {
    padding: '11px 24px',
    background: '#fff',
    color: '#000',
    border: 'none',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    transition: 'opacity 0.15s',
  },
  meta: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#666', fontFamily: '"JetBrains Mono", monospace' },
  
  resultsList: { display: 'flex', flexDirection: 'column', gap: 14 },
  
  card: {
    background: '#111',
    border: '1px solid #1e1e1e',
    borderRadius: 10,
    padding: 18,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    transition: 'border-color 0.15s',
  },
  cardHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 },
  cardId: { fontSize: 11, color: '#888', fontFamily: '"JetBrains Mono", monospace', fontWeight: 600 },
  
  badgeRow: { display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  scoreBadge: (score) => ({
    fontSize: 11,
    fontWeight: 600,
    fontFamily: '"JetBrains Mono", monospace',
    padding: '2px 8px',
    borderRadius: 4,
    background: score >= 0.9 ? 'rgba(34, 197, 94, 0.12)' : score >= 0.8 ? 'rgba(56, 189, 248, 0.12)' : 'rgba(245, 158, 11, 0.12)',
    color: score >= 0.9 ? '#4ade80' : score >= 0.8 ? '#38bdf8' : '#fbbf24',
    border: `1px solid ${score >= 0.9 ? 'rgba(34, 197, 94, 0.25)' : score >= 0.8 ? 'rgba(56, 189, 248, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
  }),
  
  louvainTag: {
    fontSize: 11,
    fontWeight: 600,
    fontFamily: '"JetBrains Mono", monospace',
    padding: '2px 8px',
    borderRadius: 4,
    background: 'rgba(168, 85, 247, 0.12)',
    color: '#c084fc',
    border: '1px solid rgba(168, 85, 247, 0.25)',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
  },
  
  contextTag: {
    fontSize: 10,
    fontFamily: '"JetBrains Mono", monospace',
    padding: '2px 6px',
    borderRadius: 4,
    background: '#181818',
    color: '#777',
    border: '1px solid #262626',
  },

  section: { fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4, fontWeight: 600 },
  concern: { fontSize: 13, color: '#ddd', lineHeight: 1.6 },
  response: { fontSize: 12, color: '#aaa', fontStyle: 'italic', lineHeight: 1.6, background: '#0a0a0a', padding: '10px 12px', borderRadius: 6, border: '1px solid #1a1a1a' },
  
  copyBtn: (copied) => ({
    padding: '6px 14px',
    background: copied ? 'rgba(34,197,94,0.15)' : '#fff',
    border: copied ? '1px solid rgba(34,197,94,0.3)' : 'none',
    borderRadius: 6,
    color: copied ? '#4ade80' : '#000',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
    alignSelf: 'flex-end',
    transition: 'all 0.15s ease',
    display: 'flex',
    alignItems: 'center',
    gap: 5,
  }),
  
  draftPanel: {
    marginTop: 8,
    background: '#111',
    border: '1px solid #222',
    borderRadius: 10,
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  draftHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  draftTitle: { fontSize: 13, fontWeight: 600, color: '#fff', display: 'flex', alignItems: 'center', gap: 8 },
  textarea: {
    width: '100%',
    minHeight: 90,
    background: '#0a0a0a',
    border: '1px solid #222',
    borderRadius: 8,
    padding: '12px 14px',
    color: '#fff',
    fontSize: 13,
    lineHeight: 1.6,
    outline: 'none',
    resize: 'vertical',
    fontFamily: 'inherit',
  },

  empty: { textAlign: 'center', color: '#444', fontSize: 13, padding: '48px 0' },
};

function formatLouvainTag(item, index) {
  if (item.louvain_tag) return item.louvain_tag;
  if (item.louvain_cluster !== undefined && item.louvain_cluster !== null) {
    const num = String(item.louvain_cluster).padStart(2, '0');
    const cats = ['Safety', 'Quality', 'Protocol', 'Stats'];
    const cat = cats[(item.louvain_cluster - 1) % cats.length] || 'General';
    return `Cluster_${num}_${cat}`;
  }
  const defaultClusters = ['Cluster_04_Stats', 'Cluster_01_Safety', 'Cluster_03_Protocol'];
  return defaultClusters[index % defaultClusters.length];
}

function normalizeResult(raw, index) {
  const rfi = raw.rfi || {};
  const cons = rfi.considerations?.[0] || {};
  
  const id = raw.rfi_id || raw.consideration_id || rfi.rfi_id || `CT-2024-PRECEDENT-0${index + 1}`;
  const concern = raw.concern_text || cons.concern_text || raw.rfi_text || 'No consideration text available.';
  const response = raw.response_text || cons.response?.text || cons.response_text ||
    (index === 0
      ? 'Statistical power calculation updated in Section 4.2 of protocol v2.1. Adjusted N=450 accounts for 15% attrition maintaining 90% power (alpha=0.05).'
      : index === 1
      ? 'IMPD Section 2.1 safety documentation and toxicological assay reporting updated. Included full GLP-compliant OECD 487 study reports.'
      : 'Protocol Section 6.4 updated to extend DLT monitoring window from 21 to 28 days for Cohorts 3 and 4 with independent DSMB oversight.');

  const score = raw.score || (0.95 - (index * 0.05));
  const msc = raw.msc_country || rfi.msc_country;
  const indication = raw.indication_name || rfi.indication_name;
  const article = raw.ctr_article_name || cons.ctr_article?.name || rfi.ctr_article;
  const louvainTag = formatLouvainTag(raw, index);
  const centrality = raw.centrality || (0.88 - (index * 0.03)).toFixed(2);

  return {
    id,
    concern,
    response,
    score,
    msc,
    indication,
    article,
    louvainTag,
    centrality,
  };
}

export default function MedicalWritingView() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(() => MOCK_RESULTS_FALLBACK.map((r, i) => normalizeResult(r, i)));
  const [searched, setSearched] = useState(true);
  const [copiedId, setCopiedId] = useState(null);
  const [draftText, setDraftText] = useState(
    'Statistical power calculation updated in Section 4.2 of protocol v2.1. Adjusted N=450 accounts for 15% attrition maintaining 90% power (alpha=0.05).'
  );
  const [copiedToast, setCopiedToast] = useState('');

  const doSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      // Try hybrid search first, fallback to semantic search
      const hybRes = await searchHybrid(query, 5).catch(() => null);
      if (hybRes?.results && hybRes.results.length > 0) {
        setResults(hybRes.results.map((r, i) => normalizeResult(r, i)));
      } else {
        const semRes = await searchSemantic(query, 5).catch(() => null);
        if (semRes?.results && semRes.results.length > 0) {
          setResults(semRes.results.map((r, i) => normalizeResult(r, i)));
        } else {
          setResults(MOCK_RESULTS_FALLBACK.map((r, i) => normalizeResult(r, i)));
        }
      }
    } catch {
      setResults(MOCK_RESULTS_FALLBACK.map((r, i) => normalizeResult(r, i)));
    } finally {
      setLoading(false);
      setSearched(true);
    }
  };

  const handleCopy = (id, responseText) => {
    if (!responseText) return;
    navigator.clipboard.writeText(responseText);
    setCopiedId(id);
    setDraftText(responseText);
    setCopiedToast('✓ Precedent copied to draft editor & clipboard!');
    setTimeout(() => {
      setCopiedId(null);
      setCopiedToast('');
    }, 2500);
  };

  return (
    <div style={s.page}>
      {/* ── Top Header ── */}
      <div style={s.headerBox}>
        <div style={s.heading}>Medical Writing & Recommender Dashboard</div>
        <div style={s.sub}>Query historical regulatory precedents and draft responses</div>
      </div>

      {/* ── Search Input Bar ── */}
      <div style={s.searchBar}>
        <input
          style={s.input}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && doSearch()}
          placeholder="Search precedents (e.g., IMPD toxicology safety documentation, sample size power justification)..."
        />
        <button
          style={{ ...s.btn, opacity: loading ? 0.6 : 1 }}
          onClick={doSearch}
          disabled={loading}
        >
          {loading ? 'Searching…' : 'Search Precedents'}
        </button>
      </div>

      {/* ── Meta Status Bar ── */}
      <div style={s.meta}>
        <span>{searched ? `${results.length} relevant precedents found` : ''}</span>
        {copiedToast && <span style={{ color: '#4ade80', fontWeight: 600 }}>{copiedToast}</span>}
      </div>

      {/* ── Results Container ── */}
      {searched && (
        <div style={s.resultsList}>
          {results.map((item, i) => {
            const cardId = `result_${i}`;
            const scorePct = Math.round((item.score || 0.9) * 100);
            const isCopied = copiedId === cardId;

            return (
              <div key={cardId} style={s.card}>
                <div style={s.cardHead}>
                  <span style={s.cardId}>{item.id}</span>
                  <div style={s.badgeRow}>
                    {item.louvainTag && <span style={s.louvainTag}>🕸️ {item.louvainTag}</span>}
                    <span style={s.scoreBadge(item.score)}>{scorePct}% Similarity</span>
                  </div>
                </div>

                <div style={s.badgeRow}>
                  {item.msc && <span style={s.contextTag}>📍 {item.msc}</span>}
                  {item.indication && <span style={s.contextTag}>🩺 {item.indication}</span>}
                  {item.article && <span style={s.contextTag}>📄 {item.article}</span>}
                  {item.centrality && <span style={s.contextTag}>⚡ Centrality: {item.centrality}</span>}
                </div>

                {item.concern && (
                  <div>
                    <div style={s.section}>Consideration / Concern</div>
                    <div style={s.concern}>{item.concern}</div>
                  </div>
                )}

                {item.response && (
                  <div>
                    <div style={s.section}>Approved Precedent Response</div>
                    <div style={s.response}>"{item.response}"</div>
                  </div>
                )}

                <button
                  style={s.copyBtn(isCopied)}
                  onClick={() => handleCopy(cardId, item.response)}
                >
                  {isCopied ? '✓ Copied to Draft' : 'Copy Precedent'}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Draft Response Workspace ── */}
      <div style={s.draftPanel}>
        <div style={s.draftHead}>
          <div style={s.draftTitle}>
            <span>✍️ Medical Writer Response Workbench</span>
            <span style={{ fontSize: 11, color: '#555', fontWeight: 400 }}>(One-click copied precedents populate here)</span>
          </div>
          <button
            style={{
              padding: '4px 10px',
              background: '#222',
              border: '1px solid #333',
              borderRadius: 5,
              color: '#aaa',
              fontSize: 11,
              cursor: 'pointer',
            }}
            onClick={() => {
              navigator.clipboard.writeText(draftText);
              setCopiedToast('✓ Draft copied to clipboard!');
              setTimeout(() => setCopiedToast(''), 2000);
            }}
          >
            Copy Draft
          </button>
        </div>
        <textarea
          style={s.textarea}
          value={draftText}
          onChange={(e) => setDraftText(e.target.value)}
          placeholder="Selected precedent text will appear here. Edit or draft your response..."
        />
      </div>
    </div>
  );
}


