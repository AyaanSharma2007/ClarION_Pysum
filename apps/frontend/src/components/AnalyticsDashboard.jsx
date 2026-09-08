import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Area, AreaChart,
} from 'recharts';
import {
  fetchAnalyticsKpis,
  fetchDepartmentMetrics,
  fetchRepeatingTopics,
  fetchAnalyticsTrends,
} from '../services/api';

// ── Custom Tooltip ───────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '10px 14px',
      boxShadow: 'var(--shadow-md)',
      fontSize: 12,
    }}>
      <p style={{ color: 'var(--text)', fontWeight: 600, marginBottom: 4 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, margin: 0 }}>
          {p.name}: <strong>{p.value}</strong>
        </p>
      ))}
    </div>
  );
};

// ── Styles ───────────────────────────────────────────────────────────────────
const s = {
  page: {
    minHeight: '100vh',
    background: 'var(--bg)',
    padding: '0 0 60px',
  },
  header: {
    borderBottom: '1px solid var(--border)',
    padding: '0 32px',
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    height: 62,
    position: 'sticky',
    top: 0,
    background: 'var(--bg)',
    zIndex: 50,
    boxShadow: 'var(--shadow-sm)',
  },
  logo: {
    fontSize: 16,
    fontWeight: 700,
    color: 'var(--text)',
    letterSpacing: '-0.02em',
  },
  backBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '7px 14px',
    fontSize: 12,
    transition: 'all 0.15s',
  },
  container: {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '28px 28px 0',
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--text)',
    marginBottom: 4,
    letterSpacing: '-0.02em',
  },
  subtitle: {
    fontSize: 13,
    color: 'var(--text-dim)',
    marginBottom: 28,
  },
  kpiRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 16,
    marginBottom: 28,
  },
  kpiCard: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 22px',
    transition: 'all 0.2s',
    boxShadow: 'var(--shadow-sm)',
  },
  kpiLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    color: 'var(--text-dim)',
    marginBottom: 8,
  },
  kpiValue: {
    fontSize: 28,
    fontWeight: 800,
    letterSpacing: '-0.03em',
  },
  kpiSub: {
    fontSize: 11,
    color: 'var(--text-muted)',
    marginTop: 4,
  },
  chartRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 20,
    marginBottom: 28,
  },
  chartCard: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 20px 12px',
    boxShadow: 'var(--shadow-sm)',
  },
  chartTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: 'var(--text)',
    marginBottom: 16,
    letterSpacing: '-0.01em',
  },
  tableCard: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 22px',
    boxShadow: 'var(--shadow-sm)',
    marginBottom: 28,
  },
  table: {
    width: '100%',
    borderCollapse: 'separate',
    borderSpacing: 0,
    fontSize: 13,
  },
  th: {
    textAlign: 'left',
    padding: '10px 14px',
    borderBottom: '2px solid var(--border)',
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    color: 'var(--text-dim)',
  },
  td: {
    padding: '12px 14px',
    borderBottom: '1px solid var(--border)',
    color: 'var(--text)',
  },
  trendBtnGroup: {
    display: 'flex',
    gap: 6,
    marginBottom: 14,
  },
  trendBtn: (active) => ({
    padding: '5px 14px',
    fontSize: 11,
    fontWeight: 600,
    border: active ? 'none' : '1px solid var(--border)',
    borderRadius: 8,
    background: active
      ? 'linear-gradient(135deg, var(--accent-blue) 0%, #6f8fff 100%)'
      : 'transparent',
    color: active ? '#fff' : 'var(--text-muted)',
    cursor: 'pointer',
    transition: 'all 0.15s',
  }),
  badge: (color) => ({
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 700,
    background: color === 'red' ? 'var(--red-light)' : color === 'amber' ? 'var(--amber-light)' : 'var(--green-light)',
    color: color === 'red' ? 'var(--red)' : color === 'amber' ? 'var(--amber)' : 'var(--green)',
  }),
  loading: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '80px 0',
    color: 'var(--text-dim)',
    fontSize: 14,
    gap: 10,
  },
  errorBanner: {
    margin: '16px 0',
    padding: '12px 18px',
    background: 'var(--red-light)',
    border: '1px solid rgba(239,83,80,0.2)',
    borderRadius: 'var(--radius-sm)',
    color: '#c62828',
    fontSize: 13,
  },
  refreshBtn: {
    marginLeft: 'auto',
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: '7px 14px',
    fontSize: 12,
    transition: 'all 0.15s',
  },
};

// Responsive: single column on narrow screens
const mediaQuery = window.matchMedia('(max-width: 800px)');

export default function AnalyticsDashboard({ onBack, showHeader = false }) {
  const [kpis, setKpis] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [topics, setTopics] = useState([]);
  const [trends, setTrends] = useState([]);
  const [trendDays, setTrendDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [narrow, setNarrow] = useState(mediaQuery.matches);

  useEffect(() => {
    const handler = (e) => setNarrow(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [kpiData, deptData, topicData, trendData] = await Promise.allSettled([
        fetchAnalyticsKpis(),
        fetchDepartmentMetrics(),
        fetchRepeatingTopics(20),
        fetchAnalyticsTrends(trendDays),
      ]);

      if (kpiData.status === 'fulfilled') setKpis(kpiData.value);
      if (deptData.status === 'fulfilled') setDepartments(deptData.value?.departments || []);
      if (topicData.status === 'fulfilled') setTopics(topicData.value?.topics || []);
      if (trendData.status === 'fulfilled') setTrends(trendData.value?.trends || []);
    } catch (e) {
      setError('Failed to load analytics data. Ensure the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [trendDays]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Reload trends when period changes
  useEffect(() => {
    (async () => {
      try {
        const data = await fetchAnalyticsTrends(trendDays);
        setTrends(data?.trends || []);
      } catch (e) { /* ignore */ }
    })();
  }, [trendDays]);

  // Chart colors
  const BLUE = '#4f72ff';
  const PINK = '#f06292';
  const GREEN = '#2db87a';
  const GRADIENT_ID = 'trendGradient';

  // Bar chart data
  const barData = (Array.isArray(departments) ? departments : []).map(d => {
    const deptName = d.department || 'Unknown';
    return {
      name: deptName.length > 18 ? deptName.slice(0, 16) + '…' : deptName,
      fullName: deptName,
      rfis: d.total_rfis || 0,
      resolved: d.resolved_count || 0,
    };
  });

  // Trend chart — aggregate weekly if > 60 days
  const rawTrends = Array.isArray(trends) ? trends : [];
  const trendData = trendDays > 60
    ? rawTrends.reduce((acc, item, i) => {
        if (i % 7 === 0) acc.push({ date: item.date, count: 0 });
        if (acc.length) acc[acc.length - 1].count += (item.count || 0);
        return acc;
      }, [])
    : rawTrends;

  if (loading) {
    return (
      <div style={s.page}>
        {showHeader && (
          <header style={s.header}>
            <div style={s.logo}>ClarION</div>
            {onBack && <button style={s.backBtn} onClick={onBack}>← RFI Repository</button>}
          </header>
        )}
        <div style={s.loading}>
          <span style={{ fontSize: 20, animation: 'spin 1.2s linear infinite', display: 'inline-block' }}>⟳</span>
          Loading analytics…
        </div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      {/* Header (rendered only when standalone showHeader=true) */}
      {showHeader && (
        <header style={s.header}>
          <div style={s.logo}>ClarION</div>
          {onBack && (
            <button
              style={s.backBtn}
              onClick={onBack}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
            >
              ← RFI Repository
            </button>
          )}
          <button
            style={s.refreshBtn}
            onClick={loadAll}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            ↻ Refresh
          </button>
        </header>
      )}

      <div style={s.container}>
        {error && <div style={s.errorBanner}>{error}</div>}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={s.title}>Analytics Dashboard</h1>
            <p style={s.subtitle}>Real-time insights into RFI trends, department performance, and recurring topics.</p>
          </div>
          <button
            style={s.refreshBtn}
            onClick={loadAll}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            ↻ Refresh Analytics
          </button>
        </div>

        {/* ── KPI Cards ──────────────────────────────────────────────────── */}
        <div style={s.kpiRow}>
          <div style={s.kpiCard}>
            <div style={s.kpiLabel}>RFIs This Month</div>
            <div style={{ ...s.kpiValue, color: BLUE }}>
              {kpis?.total_this_month ?? '—'}
            </div>
            <div style={s.kpiSub}>{kpis?.total_all_time ?? 0} total all-time</div>
          </div>

          <div style={s.kpiCard}>
            <div style={s.kpiLabel}>Redundancy Rate</div>
            <div style={{
              ...s.kpiValue,
              color: (kpis?.redundancy_rate || 0) > 30 ? '#ef5350' : (kpis?.redundancy_rate || 0) > 15 ? '#f59e0b' : GREEN,
            }}>
              {kpis?.redundancy_rate ?? 0}%
            </div>
            <div style={s.kpiSub}>
              {kpis?.duplicate_count ?? 0} duplicate{kpis?.duplicate_count !== 1 ? 's' : ''} detected
            </div>
          </div>

          <div style={s.kpiCard}>
            <div style={s.kpiLabel}>Most Problematic Dept.</div>
            <div style={{
              ...s.kpiValue,
              fontSize: 18,
              color: PINK,
              wordBreak: 'break-word',
            }}>
              {kpis?.most_problematic_department ?? 'N/A'}
            </div>
            <div style={s.kpiSub}>
              {kpis?.department_counts?.[kpis?.most_problematic_department] ?? 0} RFIs
            </div>
          </div>
        </div>

        {/* ── Charts Row ─────────────────────────────────────────────────── */}
        <div style={{
          ...s.chartRow,
          gridTemplateColumns: narrow ? '1fr' : '1fr 1fr',
        }}>
          {/* Bar Chart: Department Volume */}
          <div style={s.chartCard}>
            <div style={s.chartTitle}>RFIs per Department</div>
            {barData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    axisLine={{ stroke: 'var(--border)' }}
                    interval={0}
                    angle={-30}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    axisLine={{ stroke: 'var(--border)' }}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="rfis" name="Total RFIs" fill={BLUE} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="resolved" name="Resolved" fill={GREEN} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
                No department data available yet.
              </div>
            )}
          </div>

          {/* Line/Area Chart: RFI Volume Trends */}
          <div style={s.chartCard}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <div style={s.chartTitle}>RFI Volume Trends</div>
            </div>
            <div style={s.trendBtnGroup}>
              {[30, 60, 90].map(d => (
                <button
                  key={d}
                  style={s.trendBtn(trendDays === d)}
                  onClick={() => setTrendDays(d)}
                >
                  {d}d
                </button>
              ))}
            </div>
            {trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <defs>
                    <linearGradient id={GRADIENT_ID} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={BLUE} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={BLUE} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    axisLine={{ stroke: 'var(--border)' }}
                    tickFormatter={(val) => {
                      if (!val) return '';
                      const d = new Date(val);
                      return isNaN(d.getTime()) ? val : `${d.getMonth() + 1}/${d.getDate()}`;
                    }}
                    interval={trendDays > 60 ? 2 : Math.max(Math.floor(trendData.length / 8), 1)}
                  />
                  <YAxis
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    axisLine={{ stroke: 'var(--border)' }}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    name="RFIs"
                    stroke={BLUE}
                    strokeWidth={2}
                    fill={`url(#${GRADIENT_ID})`}
                    dot={false}
                    activeDot={{ r: 4, fill: BLUE }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
                No trend data available for this period.
              </div>
            )}
          </div>
        </div>

        {/* ── Repeating Topics Table ─────────────────────────────────────── */}
        <div style={s.tableCard}>
          <div style={s.chartTitle}>Top Repeating Questions</div>
          {topics.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>#</th>
                    <th style={s.th}>Summary</th>
                    <th style={s.th}>Department</th>
                    <th style={s.th}>Frequency</th>
                    <th style={s.th}>Similarity</th>
                  </tr>
                </thead>
                <tbody>
                  {topics.map((topic, i) => (
                    <tr
                      key={i}
                      style={{ transition: 'background 0.15s' }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <td style={{ ...s.td, color: 'var(--text-dim)', fontWeight: 600, width: 40 }}>{i + 1}</td>
                      <td style={{ ...s.td, maxWidth: 400 }}>
                        <div style={{ fontWeight: 500, lineHeight: 1.4 }}>{topic.summary}</div>
                      </td>
                      <td style={s.td}>
                        <span style={s.badge('amber')}>{topic.department}</span>
                      </td>
                      <td style={{ ...s.td, fontWeight: 700, color: PINK }}>
                        {topic.frequency}×
                      </td>
                      <td style={{ ...s.td, color: 'var(--text-muted)' }}>
                        {topic.avg_similarity
                          ? `${(topic.avg_similarity * 100).toFixed(0)}%`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
              No repeating topics detected yet. As more RFIs are ingested, duplicate patterns will appear here.
            </div>
          )}
        </div>

        {/* ── Department Detail Table ────────────────────────────────────── */}
        {departments.length > 0 && (
          <div style={s.tableCard}>
            <div style={s.chartTitle}>Department Performance</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Department</th>
                    <th style={s.th}>Total RFIs</th>
                    <th style={s.th}>Resolved</th>
                    <th style={s.th}>Unresolved</th>
                    <th style={s.th}>Avg. Resolution (hrs)</th>
                  </tr>
                </thead>
                <tbody>
                  {departments.map((d, i) => (
                    <tr
                      key={i}
                      onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <td style={{ ...s.td, fontWeight: 600 }}>{d.department}</td>
                      <td style={{ ...s.td, fontWeight: 700, color: BLUE }}>{d.total_rfis}</td>
                      <td style={s.td}>
                        <span style={s.badge('green')}>{d.resolved_count}</span>
                      </td>
                      <td style={s.td}>
                        <span style={s.badge(d.unresolved_count > 5 ? 'red' : 'amber')}>
                          {d.unresolved_count}
                        </span>
                      </td>
                      <td style={{ ...s.td, color: 'var(--text-muted)' }}>
                        {d.avg_resolution_hours != null ? `${d.avg_resolution_hours}h` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
