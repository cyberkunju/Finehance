/**
 * Dashboard Page
 * 
 * Main dashboard showing financial overview, advice, and key metrics.
 */

import { useQuery } from '@tanstack/react-query';
import { Chart as ChartJS, ArcElement, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend } from 'chart.js';
import { Pie, Bar } from 'react-chartjs-2';
import { useAuth } from '../contexts/AuthContext';
import { getDashboardSummary } from '../api/dashboard';
import { getPersonalizedAdvice } from '../api/advice';
import { generateReport } from '../api/reports';
import { AdvicePriority } from '../types';
import './DashboardPage.css';

// Register Chart.js components
ChartJS.register(ArcElement, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend);

function DashboardPage() {
  const { user } = useAuth();

  // Fetch dashboard summary
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useQuery({
    queryKey: ['dashboard-summary', user?.id],
    queryFn: () => getDashboardSummary(user!.id),
    enabled: !!user,
  });

  // Fetch personalized advice
  const { data: advice, isLoading: adviceLoading } = useQuery({
    queryKey: ['dashboard-advice', user?.id],
    queryFn: () => getPersonalizedAdvice(user!.id, 3),
    enabled: !!user,
  });

  // Fetch current month report for charts
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

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Get priority color
  const getPriorityColor = (priority: AdvicePriority) => {
    switch (priority) {
      case AdvicePriority.CRITICAL:
        return '#dc3545';
      case AdvicePriority.HIGH:
        return '#fd7e14';
      case AdvicePriority.MEDIUM:
        return '#ffc107';
      case AdvicePriority.LOW:
        return '#28a745';
      default:
        return '#6c757d';
    }
  };

  // Parse expense breakdown from nested structure
  const expenseBreakdown = report?.expense_summary?.expenses_by_category || {};
  const expenseChartData = report && Object.keys(expenseBreakdown).length > 0 ? {
    labels: Object.keys(expenseBreakdown),
    datasets: [{
      label: 'Expenses by Category',
      data: Object.values(expenseBreakdown).map(v => parseFloat(String(v))),
      backgroundColor: [
        '#FF6384',
        '#36A2EB',
        '#FFCE56',
        '#4BC0C0',
        '#9966FF',
        '#FF9F40',
        '#FF6384',
        '#C9CBCF',
      ],
    }],
  } : null;

  // Parse income vs expenses from nested structure
  const totalIncome = parseFloat(String(report?.income_summary?.total_income || 0));
  const totalExpenses = parseFloat(String(report?.expense_summary?.total_expenses || 0));
  const incomeExpenseChartData = report ? {
    labels: ['Income', 'Expenses'],
    datasets: [{
      label: 'This Month',
      data: [totalIncome, totalExpenses],
      backgroundColor: ['#28a745', '#dc3545'],
    }],
  } : null;

  if (summaryLoading || adviceLoading || reportLoading) {
    return (
      <div className="dashboard-page">
        <h1>Dashboard</h1>
        <p className="subtitle">Loading your financial overview...</p>
      </div>
    );
  }

  if (summaryError) {
    return (
      <div className="dashboard-page">
        <h1>Dashboard</h1>
        <p className="subtitle error">Failed to load dashboard data. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <h1>Dashboard</h1>
      <p className="subtitle">Your financial overview at a glance</p>

      <div className="dashboard-grid">
        <div className="card">
          <h3>💰 Net Savings</h3>
          <p className="metric">{formatCurrency(summary?.this_month_net || 0)}</p>
          <small>This month</small>
        </div>

        <div className="card">
          <h3>📊 Income vs Expenses</h3>
          <p className="metric">{formatCurrency(summary?.this_month_income || 0)}</p>
          <small>Income: {formatCurrency(summary?.this_month_income || 0)} | Expenses: {formatCurrency(summary?.this_month_expenses || 0)}</small>
        </div>

        <div className="card">
          <h3>🎯 Goals Progress</h3>
          <p className="metric">{(summary?.goals_progress_avg || 0).toFixed(1)}%</p>
          <small>{summary?.active_goals_count || 0} active goals</small>
        </div>

        <div className="card">
          <h3>💳 Transactions</h3>
          <p className="metric">{summary?.transaction_count || 0}</p>
          <small>This month</small>
        </div>
      </div>

      <div className="advice-section">
        <h2>💡 Personalized Advice</h2>
        {advice && advice.length > 0 ? (
          <div className="advice-list">
            {advice.map((item, index) => (
              <div
                key={index}
                className="advice-card"
                style={{ borderLeft: `4px solid ${getPriorityColor(item.priority)}` }}
              >
                <div className="advice-header">
                  <h3>{item.title}</h3>
                  <span className="advice-priority" style={{ color: getPriorityColor(item.priority) }}>
                    {item.priority}
                  </span>
                </div>
                <p className="advice-message">{item.message}</p>
                {item.explanation && (
                  <p className="advice-explanation">{item.explanation}</p>
                )}
                {item.action_items && item.action_items.length > 0 && (
                  <ul className="advice-actions">
                    {item.action_items.map((action, i) => (
                      <li key={i}>{action}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="advice-card">
            <p>Start by adding your first transaction to get personalized financial advice!</p>
          </div>
        )}
      </div>

      <div className="charts-section">
        <h2>📈 Spending Analysis</h2>
        {report && Object.keys(expenseBreakdown).length > 0 ? (
          <div className="charts-grid">
            <div className="chart-card">
              <h3>Expenses by Category</h3>
              {expenseChartData && <Pie data={expenseChartData} />}
            </div>
            <div className="chart-card">
              <h3>Income vs Expenses</h3>
              {incomeExpenseChartData && <Bar data={incomeExpenseChartData} />}
            </div>
          </div>
        ) : (
          <div className="chart-placeholder">
            <p>Charts will appear here once you have transaction data</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;
