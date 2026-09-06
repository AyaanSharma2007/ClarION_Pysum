import React, { useMemo } from 'react';

const STAGES = [
  { value: 'all', label: 'All Stages' },
  { value: 'received', label: 'Received' },
  { value: 'RA_Clinical_Review', label: 'RA Review' },
  { value: 'CTA_Mgmt_Review', label: 'CTA Review' },
  { value: 'EU_Hub_Approval', label: 'EU Approval' },
  { value: 'Submitted', label: 'Submitted' },
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
    background: '#fff',
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
    background: '#fff',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '9px 12px',
    color: 'var(--text-muted)',
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
  const countryOptions = useMemo(
    () => [{ value: 'all', label: 'All Countries' }, ...countries.map(c => ({ value: c, label: c }))],
    [countries]
  );

  const set = (key) => (e) => setFilters(f => ({ ...f, [key]: e.target.value }));

  return (
    <div style={s.bar}>
      <div style={s.searchWrap}>
        <span style={s.searchIcon}>🔍</span>
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

      <div style={s.countBadge}>{resultCount} RFI{resultCount !== 1 ? 's' : ''}</div>
    </div>
  );
}
