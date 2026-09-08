import React, { useMemo } from 'react';

const STAGES = [
  { value: 'all', label: 'All Stages' },
  { value: 'awaiting_response', label: 'Awaiting Response' },
  { value: 'drafting', label: 'Drafting' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'received', label: 'Received' },
];

const CATEGORIES = [
  { value: 'all', label: 'All Categories' },
  { value: 'IMPD Safety', label: 'IMPD Safety' },
  { value: 'Statistics', label: 'Statistics' },
  { value: 'Protocol Design', label: 'Protocol Design' },
  { value: 'Pharmacology', label: 'Pharmacology' },
  { value: 'Clinical', label: 'Clinical' },
];

const SORTS = [
  { value: 'sla_asc', label: 'Deadline — Soonest First' },
  { value: 'received_desc', label: 'Newest Received' },
  { value: 'country_asc', label: 'Country A → Z' },
  { value: 'risk_desc', label: 'Highest Risk First' },
];

const s = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '14px 0 10px',
    flexWrap: 'wrap',
  },
  searchWrap: {
    position: 'relative',
    flex: '1 1 260px',
    minWidth: 200,
  },
  searchIcon: {
    position: 'absolute',
    left: 12,
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--text-dim)',
    fontSize: 13,
    pointerEvents: 'none',
  },
  search: {
    width: '100%',
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '9px 12px 9px 34px',
    color: 'var(--text)',
    outline: 'none',
    fontSize: 13,
    transition: 'all 0.15s',
    boxShadow: 'var(--shadow-sm)',
  },
  select: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '9px 12px',
    color: 'var(--text)',
    outline: 'none',
    fontSize: 12,
    cursor: 'pointer',
    flex: '0 1 auto',
    boxShadow: 'var(--shadow-sm)',
  },
  countBadge: {
    marginLeft: 'auto',
    fontSize: 12,
    whiteSpace: 'nowrap',
    padding: '6px 12px',
    background: 'var(--accent-blue-light)',
    borderRadius: 'var(--radius-lg)',
    fontWeight: 600,
    color: 'var(--accent-blue)',
  },
};

export default function FilterBar({ filters, setFilters, countries, resultCount }) {
  const [expanded, setExpanded] = React.useState(false);

  const countryOptions = useMemo(
    () => [{ value: 'all', label: 'All Countries' }, ...countries.map(c => ({ value: c, label: c }))],
    [countries]
  );

  const set = (key) => (e) => setFilters(f => ({ ...f, [key]: e.target.value }));

  const activeExtraFiltersCount = [
    filters.date,
    filters.trialId,
    filters.euCtNumber,
    filters.protocolCode,
    filters.imp,
    filters.therapeuticArea,
    filters.rms,
    filters.trialPhase,
    filters.docType,
    filters.proofOfPayment,
    filters.protocol,
    filters.icf,
  ].filter(Boolean).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '14px 0 10px' }}>
      <div style={s.bar}>
        <div style={s.searchWrap}>
          <span style={s.searchIcon}></span>
          <input
            id="rfi-search"
            style={s.search}
            type="text"
            placeholder="Search by RFI ID, country, indication, concern..."
            value={filters.query}
            onChange={set('query')}
            onFocus={e => { e.target.style.borderColor = 'var(--accent-blue)'; e.target.style.boxShadow = '0 0 0 3px rgba(79,114,255,0.12)'; }}
            onBlur={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'var(--shadow-sm)'; }}
          />
        </div>

        <select id="filter-country" style={s.select} value={filters.country} onChange={set('country')}>
          {countryOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <select id="filter-stage" style={s.select} value={filters.stage} onChange={set('stage')}>
          {STAGES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <select id="filter-category" style={s.select} value={filters.category} onChange={set('category')}>
          {CATEGORIES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <select id="filter-sort" style={s.select} value={filters.sort} onChange={set('sort')}>
          {SORTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <button
          id="toggle-advanced-filters-btn"
          style={{
            ...s.select,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontWeight: 600,
            background: expanded ? 'var(--accent-blue-light)' : 'var(--bg-card)',
            color: expanded ? 'var(--accent-blue)' : 'var(--text)',
            borderColor: expanded ? 'var(--accent-blue)' : 'var(--border)',
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <span> Filters</span>
          {activeExtraFiltersCount > 0 && (
            <span style={{
              background: 'var(--accent-blue)',
              color: '#fff',
              fontSize: 10,
              padding: '1px 6px',
              borderRadius: 10,
            }}>
              {activeExtraFiltersCount}
            </span>
          )}
          <span>{expanded ? '' : '▼'}</span>
        </button>

        <div style={s.countBadge}>{resultCount} RFI{resultCount !== 1 ? 's' : ''}</div>
      </div>

      {expanded && (
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          padding: '16px 18px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 12,
          animation: 'fadeIn 0.2s ease',
        }}>
          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Date (Submit / Due)</label>
            <input
              type="date"
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              value={filters.date || ''}
              onChange={set('date')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Trial ID</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. TRIAL-101..."
              value={filters.trialId || ''}
              onChange={set('trialId')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>EU-CT Number</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. 2024-500..."
              value={filters.euCtNumber || ''}
              onChange={set('euCtNumber')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Protocol Code</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. PROTO-01..."
              value={filters.protocolCode || ''}
              onChange={set('protocolCode')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Investigational Med Product</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. IMP-X / Molecule..."
              value={filters.imp || ''}
              onChange={set('imp')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Therapeutic Area</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. Oncology, Diabetes..."
              value={filters.therapeuticArea || ''}
              onChange={set('therapeuticArea')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>RMS (Ref Member State)</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. Germany, France..."
              value={filters.rms || ''}
              onChange={set('rms')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Trial Phase</label>
            <select
              style={{ ...s.select, width: '100%', padding: '7px 10px' }}
              value={filters.trialPhase || 'all'}
              onChange={set('trialPhase')}
            >
              <option value="all">All Phases</option>
              <option value="Phase I">Phase I</option>
              <option value="Phase II">Phase II</option>
              <option value="Phase III">Phase III</option>
              <option value="Phase IV">Phase IV</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Requested Document Type</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="e.g. Protocol, ICF, IMPD..."
              value={filters.docType || ''}
              onChange={set('docType')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Proof of Payment</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="Receipt / Payment ref..."
              value={filters.proofOfPayment || ''}
              onChange={set('proofOfPayment')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>Protocol</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="Filter by protocol name..."
              value={filters.protocol || ''}
              onChange={set('protocol')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 4 }}>ICF (Informed Consent)</label>
            <input
              style={{ ...s.search, padding: '7px 10px', fontSize: 12 }}
              placeholder="Filter by ICF details..."
              value={filters.icf || ''}
              onChange={set('icf')}
            />
          </div>

          {activeExtraFiltersCount > 0 && (
            <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
              <button
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--red)',
                  fontSize: 12,
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
                onClick={() => setFilters(f => ({
                  ...f,
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
                }))}
              >
                Reset Advanced Filters
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
