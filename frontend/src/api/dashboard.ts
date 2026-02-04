/**
 * Dashboard API Service
 * 
 * API calls for dashboard summary statistics and metrics.
 */

import apiClient from './client';

// Backend report response structure
interface BackendReportResponse {
  report_id: string;
  user_id: string;
  start_date: string;
  end_date: string;
  income_summary: {
    total_income: string | number;
    income_by_category: Record<string, string | number>;
    transaction_count: number;
  };
  expense_summary: {
    total_expenses: string | number;
    expenses_by_category: Record<string, string | number>;
    transaction_count: number;
    average_transaction: string | number;
  };
  net_savings: string | number;
  savings_rate: number;
  budget_adherence: Record<string, number> | null;
  spending_changes: any[];
  generated_at: string;
}

export interface DashboardSummary {
  total_balance: number;
  this_month_income: number;
  this_month_expenses: number;
  this_month_net: number;
  transaction_count: number;
  active_goals_count: number;
  goals_progress_avg: number;
}

/**
 * Get dashboard summary statistics
 */
export const getDashboardSummary = async (userId: string): Promise<DashboardSummary> => {
  // Get current month date range
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

  const startDate = startOfMonth.toISOString().split('T')[0];
  const endDate = endOfMonth.toISOString().split('T')[0];

  // Fetch current month report
  const response = await apiClient.post<BackendReportResponse>('/api/reports/generate', {
    user_id: userId,
    start_date: startDate,
    end_date: endDate,
  });

  const report = response.data;

  // Parse values from nested structure (they might be strings from Decimal)
  const totalIncome = parseFloat(String(report.income_summary?.total_income || 0));
  const totalExpenses = parseFloat(String(report.expense_summary?.total_expenses || 0));
  const netSavings = parseFloat(String(report.net_savings || 0));
  const transactionCount = (report.income_summary?.transaction_count || 0) +
    (report.expense_summary?.transaction_count || 0);

  // Fetch goals to calculate progress
  const goalsResponse = await apiClient.get('/api/goals', {
    params: { user_id: userId, status: 'ACTIVE' },
  });

  const goals = goalsResponse.data || [];
  const activeGoalsCount = Array.isArray(goals) ? goals.length : 0;
  const goalsProgressAvg = activeGoalsCount > 0
    ? goals.reduce((sum: number, goal: any) => {
      const progress = (goal.current_amount / goal.target_amount) * 100;
      return sum + Math.min(progress, 100);
    }, 0) / activeGoalsCount
    : 0;

  return {
    total_balance: netSavings,
    this_month_income: totalIncome,
    this_month_expenses: totalExpenses,
    this_month_net: netSavings,
    transaction_count: transactionCount,
    active_goals_count: activeGoalsCount,
    goals_progress_avg: goalsProgressAvg,
  };
};
