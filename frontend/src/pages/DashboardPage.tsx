/**
 * Dashboard Page
 *
 * Premium financial dashboard with compact, data-dense visualizations,
 * glass-morphism accents, and a tight consistent grid system.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  RadialBarChart,
  RadialBar,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  Activity,
  CreditCard,
  Calendar,
  PiggyBank,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { usePreferences } from '../contexts/PreferencesContext';
import { useTheme } from '../contexts/ThemeContext';
import { getDashboardSummary } from '../api/dashboard';
import { getPersonalizedAdvice } from '../api/advice';
import { generateReport } from '../api/reports';

import './DashboardPage.css';

// Desaturated, muted palette — subtle hint of hue, not vivid
const CHART_PALETTE_DARK = [
  '#8b8fa8', // muted steel-blue
  '#8a9a8e', // sage
  '#a89b8b', // warm taupe
  '#9b8b9e', // dusty mauve
  '#8ba09b', // muted teal
  '#a09088', // stone
  '#9298a8', // slate
  '#a8a08b', // khaki
];

const CHART_PALETTE_LIGHT = [
  '#6b7080', // steel
  '#607060', // olive
  '#806b5b', // taupe
  '#706078', // mauve
  '#5b7570', // teal
  '#787068', // stone
  '#606878', // slate
  '#78755b', // khaki
];

/* ── Tooltip ── */
function ChartTooltip({ active, payload, label, formatter }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="dash-tooltip">
      {label && <p className="dash-tooltip__label">{label}</p>}
      {payload.map((entry: any, i: number) => (
        <div key={i} className="dash-tooltip__row">
          <span className="dash-tooltip__dot" style={{ background: entry.color || entry.fill }} />
          <span className="dash-tooltip__name">{entry.name}</span>
          <span className="dash-tooltip__val">
            {formatter ? formatter(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ================================================================ */

function DashboardPage() {
  const { user } = useAuth();
  const { formatCurrency } = usePreferences();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const chartPalette = isDark ? CHART_PALETTE_DARK : CHART_PALETTE_LIGHT;

  /* ── Queries ── */
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useQuery({
    queryKey: ['dashboard-summary', user?.id],
    queryFn: () => getDashboardSummary(user!.id),
    enabled: !!user,
  });

  const { data: advice } = useQuery({
    queryKey: ['dashboard-advice', user?.id],
    queryFn: () => getPersonalizedAdvice(user!.id, 4),
    enabled: !!user,
  });

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ['dashboard-report', user?.id],
    queryFn: async () => {
      const now = new Date();
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
      const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      return generateReport({
        user_id: user!.id,
        start_date: startOfMonth.toISOString().split('T')[0],
        end_date: endOfMonth.toISOString().split('T')[0],
      });
    },
    enabled: !!user,
  });

  /* ── Derived Metrics ── */
  const totalIncome = summary?.this_month_income || 0;
  const totalExpenses = summary?.this_month_expenses || 0;
  const netSavings = summary?.this_month_net || 0;
  const savingsRate = totalIncome > 0 ? (netSavings / totalIncome) * 100 : 0;
  const txCount = summary?.transaction_count || 0;
  const goalCount = summary?.active_goals_count || 0;
  const goalProgress = summary?.goals_progress_avg || 0;

  /* ── Chart Data ── */
  const categoryData = useMemo(() => {
    if (!report?.expense_summary?.expenses_by_category) return [];
    const data = Object.entries(report.expense_summary.expenses_by_category)
      .map(([name, value]) => ({ name, value: Number(value) }))
      .filter(item => item.value > 0)
      .sort((a, b) => b.value - a.value);
    if (data.length <= 6) return data;
    const top = data.slice(0, 5);
    const other = data.slice(5).reduce((acc, curr) => acc + curr.value, 0);
    return [...top, { name: 'Other', value: other }];
  }, [report]);

  // Savings radial for the gauge
  const savingsRadial = useMemo(() => {
    const clamped = Math.max(0, Math.min(100, savingsRate));
    const fill = savingsRate >= 20 ? (isDark ? '#7a9a85' : '#5a7a65') : (isDark ? '#a09080' : '#887868');
    return [{ name: 'Savings', value: clamped, fill }];
  }, [savingsRate, isDark]);

  /* ── Loading / Error ── */
  if (summaryLoading || reportLoading) {
    return (
      <div className="dash-loading">
        <div className="dash-loading__spinner" />
        <p>Loading your financial overview…</p>
      </div>
    );
  }
  if (summaryError) {
    return <div className="dash-error">Unable to load dashboard. Please try again.</div>;
  }

  /* ── Helpers ── */
  const shortCurrency = (v: number) => {
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
    return formatCurrency(v);
  };

  const priorityMarker = (p: string) => {
    switch (p?.toLowerCase()) {
      case 'critical': return '◆';
      case 'high': return '▲';
      case 'medium': return '●';
      default: return '○';
    }
  };

  return (
    <div className="dash">
      {/* ═══════════ Header ═══════════ */}
      <header className="dash__header">
        <div>
          <h1 className="dash__title">Dashboard</h1>
          <p className="dash__subtitle">Your financial overview at a glance</p>
        </div>
        <div className="dash__header-actions">
          <span className="dash__date-pill">
            <Calendar size={13} />
            {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' }).toUpperCase()}
          </span>
        </div>
      </header>

      {/* ═══════════ KPI Strip ═══════════ */}
      <section className="dash__kpi-strip">
        {/* Net Savings */}
        <div className="kpi">
          <div className="kpi__icon kpi__icon--savings"><PiggyBank size={20} /></div>
          <div className="kpi__body">
            <span className="kpi__label">Net Savings</span>
            <span className={`kpi__value ${netSavings >= 0 ? 'kpi__value--pos' : 'kpi__value--neg'}`}>
              {formatCurrency(netSavings)}
            </span>
            <span className={`kpi__delta ${netSavings >= 0 ? 'kpi__delta--pos' : 'kpi__delta--neg'}`}>
              {netSavings >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {netSavings >= 0 ? 'Surplus' : 'Deficit'}
            </span>
          </div>
        </div>

        {/* Income */}
        <div className="kpi">
          <div className="kpi__icon kpi__icon--income"><TrendingUp size={20} /></div>
          <div className="kpi__body">
            <span className="kpi__label">Income</span>
            <span className="kpi__value">{formatCurrency(totalIncome)}</span>
            <span className="kpi__delta kpi__delta--pos">
              <ArrowUpRight size={12} /> This month
            </span>
          </div>
        </div>

        {/* Expenses */}
        <div className="kpi">
          <div className="kpi__icon kpi__icon--expense"><TrendingDown size={20} /></div>
          <div className="kpi__body">
            <span className="kpi__label">Expenses</span>
            <span className="kpi__value">{formatCurrency(totalExpenses)}</span>
            <span className="kpi__delta kpi__delta--neg">
              <ArrowDownRight size={12} /> This month
            </span>
          </div>
        </div>

        {/* Goals */}
        <div className="kpi">
          <div className="kpi__icon kpi__icon--goals"><Target size={20} /></div>
          <div className="kpi__body">
            <span className="kpi__label">Goals</span>
            <span className="kpi__value">{goalCount > 0 ? `${goalProgress.toFixed(0)}%` : '0'}</span>
            <span className="kpi__delta kpi__delta--neutral">
              {goalCount} active
            </span>
          </div>
        </div>

        {/* Transactions */}
        <div className="kpi">
          <div className="kpi__icon kpi__icon--tx"><CreditCard size={20} /></div>
          <div className="kpi__body">
            <span className="kpi__label">Transactions</span>
            <span className="kpi__value">{txCount}</span>
            <span className="kpi__delta kpi__delta--neutral">This month</span>
          </div>
        </div>
      </section>

      {/* ═══════════ Main Grid ═══════════ */}
      <section className="dash__grid">

        {/* ── Spending Breakdown (Donut) ── */}
        <div className="dash-card dash-card--breakdown">
          <div className="dash-card__head">
            <h3>Spending Breakdown</h3>
            <span className="dash-card__subtitle">Where your money goes</span>
          </div>
          <div className="breakdown__body">
            <div className="breakdown__donut">
              <ResponsiveContainer width="100%" height={190}>
                <PieChart>
                  <Pie
                    data={categoryData.length > 0 ? categoryData : [{ name: 'No data', value: 1 }]}
                    cx="50%"
                    cy="50%"
                    innerRadius={58}
                    outerRadius={82}
                    paddingAngle={categoryData.length > 1 ? 4 : 0}
                    dataKey="value"
                    strokeWidth={0}
                    startAngle={90}
                    endAngle={-270}
                  >
                    {(categoryData.length > 0 ? categoryData : [{ name: 'No data', value: 1 }]).map((_, i) => (
                      <Cell
                        key={i}
                        fill={categoryData.length > 0 ? chartPalette[i % chartPalette.length] : (isDark ? '#252525' : '#e0e0e0')}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip formatter={formatCurrency} />} />
                  <text
                    x="50%"
                    y="46%"
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={isDark ? '#fff' : '#111'}
                    fontSize={18}
                    fontWeight={700}
                    style={{ fontFamily: 'var(--font-family)' }}
                  >
                    {shortCurrency(totalExpenses)}
                  </text>
                  <text
                    x="50%"
                    y="58%"
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={isDark ? '#555' : '#aaa'}
                    fontSize={10}
                    fontWeight={600}
                    letterSpacing={1.5}
                  >
                    TOTAL
                  </text>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="breakdown__legend">
              {categoryData.map((entry, i) => {
                const pct = totalExpenses > 0 ? ((entry.value / totalExpenses) * 100) : 0;
                return (
                  <div key={i} className="legend-row">
                    <div className="legend-row__left">
                      <span className="legend-dot" style={{ background: chartPalette[i % chartPalette.length] }} />
                      <span className="legend-name">{entry.name}</span>
                    </div>
                    <div className="legend-row__right">
                      <span className="legend-amount">{formatCurrency(entry.value)}</span>
                      <span className="legend-pct">{pct.toFixed(1)}%</span>
                    </div>
                  </div>
                );
              })}
              {categoryData.length === 0 && (
                <p className="legend-empty">No spending data yet</p>
              )}
            </div>
          </div>
        </div>

        {/* ── Cash Flow ── */}
        <div className="dash-card dash-card--cashflow">
          <div className="dash-card__head">
            <h3>Cash Flow</h3>
            <span className="dash-card__subtitle">Income vs Expenses</span>
          </div>
          <div className="cashflow__visual">
            {/* Income bar */}
            <div className="cf-row">
              <div className="cf-row__meta">
                <span className="cf-dot cf-dot--income" />
                <span className="cf-label">Income</span>
              </div>
              <div className="cf-bar-track">
                <div
                  className="cf-bar cf-bar--income"
                  style={{ width: `${totalIncome > 0 || totalExpenses > 0 ? Math.max(3, (totalIncome / Math.max(totalIncome, totalExpenses)) * 100) : 3}%` }}
                />
              </div>
              <span className="cf-amount">{formatCurrency(totalIncome)}</span>
            </div>
            {/* Expense bar */}
            <div className="cf-row">
              <div className="cf-row__meta">
                <span className="cf-dot cf-dot--expense" />
                <span className="cf-label">Expenses</span>
              </div>
              <div className="cf-bar-track">
                <div
                  className="cf-bar cf-bar--expense"
                  style={{ width: `${totalIncome > 0 || totalExpenses > 0 ? Math.max(3, (totalExpenses / Math.max(totalIncome, totalExpenses)) * 100) : 3}%` }}
                />
              </div>
              <span className="cf-amount">{formatCurrency(totalExpenses)}</span>
            </div>
            {/* Balance summary */}
            <div className={`cf-balance ${netSavings >= 0 ? 'cf-balance--pos' : 'cf-balance--neg'}`}>
              <span className="cf-balance__label">{netSavings >= 0 ? 'SURPLUS' : 'OVERSPENT BY'}</span>
              <span className="cf-balance__value">{formatCurrency(Math.abs(netSavings))}</span>
            </div>
          </div>
        </div>

        {/* ── Top Categories (Horizontal bars) ── */}
        <div className="dash-card dash-card--topcats">
          <div className="dash-card__head">
            <h3>Top Categories</h3>
            <span className="dash-card__subtitle">Highest spending areas</span>
          </div>
          <div className="topcats__body">
            {categoryData.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(120, categoryData.length * 34)}>
                <BarChart
                  data={categoryData}
                  layout="vertical"
                  margin={{ top: 0, right: 12, left: 0, bottom: 0 }}
                  barSize={12}
                >
                  <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={isDark ? '#1e1e1e' : '#eee'} />
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    width={85}
                    tick={{ fill: isDark ? '#777' : '#888', fontSize: 11, fontWeight: 500 }}
                  />
                  <Tooltip content={<ChartTooltip formatter={formatCurrency} />} cursor={{ fill: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)' }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} animationDuration={800}>
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={chartPalette[i % chartPalette.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="topcats__empty">No category data available</p>
            )}
          </div>
        </div>

        {/* ── Savings Rate Gauge ── */}
        <div className="dash-card dash-card--gauge">
          <div className="dash-card__head">
            <h3>Savings Rate</h3>
            <span className="dash-card__subtitle">Percentage of income saved</span>
          </div>
          <div className="gauge__body">
            <ResponsiveContainer width="100%" height={150}>
              <RadialBarChart
                cx="50%"
                cy="50%"
                innerRadius="64%"
                outerRadius="100%"
                startAngle={180}
                endAngle={0}
                data={savingsRadial}
                barSize={10}
              >
                <RadialBar
                  background={{ fill: isDark ? '#1e1e1e' : '#e8e8e8' }}
                  dataKey="value"
                  cornerRadius={6}
                  animationDuration={1200}
                />
                {/* Center label */}
                <text
                  x="50%"
                  y="44%"
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={isDark ? '#fff' : '#111'}
                  fontSize={20}
                  fontWeight={700}
                  style={{ fontFamily: 'var(--font-family)' }}
                >
                  {savingsRate.toFixed(1)}%
                </text>
                <text
                  x="50%"
                  y="58%"
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={isDark ? '#555' : '#aaa'}
                  fontSize={10}
                  fontWeight={600}
                  letterSpacing={1.5}
                >
                  SAVED
                </text>
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="gauge__footer">
              <div className="gauge__stat">
                <span className="gauge__stat-label">Earned</span>
                <span className="gauge__stat-value">{formatCurrency(totalIncome)}</span>
              </div>
              <div className="gauge__divider" />
              <div className="gauge__stat">
                <span className="gauge__stat-label">Saved</span>
                <span className="gauge__stat-value">{formatCurrency(Math.max(0, netSavings))}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════ AI Insights ═══════════ */}
      <section className="dash__insights">
        <div className="dash__insights-head">
          <Zap size={16} className="insights-icon" />
          <h3>AI Insights</h3>
          <span className="dash__insights-sub">Personalized recommendations for your finances</span>
        </div>
        <div className="insights-grid">
          {advice && advice.length > 0 ? (
            advice.map((item, idx) => (
              <div key={idx} className={`insight-card insight-card--${(item.priority || 'low').toLowerCase()}`}>
                <div className="insight-card__top">
                  <span className="insight-card__marker">{priorityMarker(item.priority)}</span>
                  <span className={`insight-badge insight-badge--${(item.priority || 'low').toLowerCase()}`}>
                    {(item.priority || 'LOW').toUpperCase()}
                  </span>
                </div>
                <h4 className="insight-card__title">{item.title}</h4>
                <p className="insight-card__desc">{item.message}</p>
                <div className="insight-card__actions">
                  {item.action_items?.slice(0, 3).map((step: string, si: number) => (
                    <div key={si} className="insight-step">
                      <ChevronRight size={12} />
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <div className="insights-empty">
              <Activity size={28} />
              <p>Add more data to unlock AI insights</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default DashboardPage;
