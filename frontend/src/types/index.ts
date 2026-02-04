/**
 * TypeScript type definitions for the AI Finance Platform
 */

// User types
export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: TokenResponse;
}

// Transaction types
export const TransactionType = {
  INCOME: 'INCOME',
  EXPENSE: 'EXPENSE',
} as const;

export type TransactionType = typeof TransactionType[keyof typeof TransactionType];

export const TransactionSource = {
  MANUAL: 'MANUAL',
  API: 'API',
  FILE_IMPORT: 'FILE_IMPORT',
} as const;

export type TransactionSource = typeof TransactionSource[keyof typeof TransactionSource];

export interface Transaction {
  id: string;
  user_id: string;
  amount: number;
  date: string;
  description: string;
  category: string;
  type: TransactionType;
  source: TransactionSource;
  confidence_score?: number;
  created_at: string;
  updated_at: string;
}

export interface TransactionCreate {
  amount: number;
  date: string;
  description: string;
  type: TransactionType;
  category?: string;
  source?: TransactionSource;
}

export interface TransactionFilters {
  start_date?: string;
  end_date?: string;
  category?: string;
  type?: TransactionType;
  min_amount?: number;
  max_amount?: number;
  search?: string;
}

// Budget types
export interface Budget {
  id: string;
  user_id: string;
  name: string;
  period_start: string;
  period_end: string;
  allocations: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface BudgetCreate {
  name: string;
  period_start: string;
  period_end: string;
  allocations: Record<string, number>;
}

export interface BudgetProgress {
  progress: Record<string, CategoryProgress>;
  alerts: BudgetAlert[];
}

export interface CategoryProgress {
  category: string;
  allocated: number;
  spent: number;
  remaining: number;
  percent_used: number;
  status: string;
}

export interface BudgetAlert {
  category: string;
  allocated: number;
  spent: number;
  percent_over: number;
  severity: string;
  message: string;
}

export interface BudgetOptimization {
  category: string;
  current_allocation: number;
  suggested_allocation: number;
  change_amount: number;
  change_percent: number;
  reason: string;
  priority: string;
}

// Goal types
export const GoalStatus = {
  ACTIVE: 'ACTIVE',
  ACHIEVED: 'ACHIEVED',
  ARCHIVED: 'ARCHIVED',
} as const;

export type GoalStatus = typeof GoalStatus[keyof typeof GoalStatus];

export interface FinancialGoal {
  id: string;
  user_id: string;
  name: string;
  target_amount: number;
  current_amount: number;
  deadline?: string;
  category?: string;
  status: GoalStatus;
  created_at: string;
  updated_at: string;
}

export interface GoalCreate {
  name: string;
  target_amount: number;
  deadline?: string;
  category?: string;
  current_amount?: number;
}

export interface GoalProgress {
  goal_id: string;
  progress_percentage: number;
  estimated_completion_date?: string;
  is_at_risk: boolean;
  days_remaining?: number;
}

// Prediction types
export interface ForecastResult {
  category: string;
  predictions: number[];
  dates: string[];
  confidence_intervals: {
    lower: number[];
    upper: number[];
  };
  accuracy_note?: string;
}

export interface Anomaly {
  date: string;
  amount: number;
  category: string;
  expected_amount: number;
  deviation_percentage: number;
}

// Advice types
export const AdvicePriority = {
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
  LOW: 'LOW',
} as const;

export type AdvicePriority = typeof AdvicePriority[keyof typeof AdvicePriority];

export interface Advice {
  title: string;
  message: string;
  priority: AdvicePriority;
  category?: string;
  explanation: string;
  action_items?: string[];
}

// Report types
export interface IncomeSummary {
  total_income: number | string;
  income_by_category: Record<string, number | string>;
  transaction_count: number;
}

export interface ExpenseSummary {
  total_expenses: number | string;
  expenses_by_category: Record<string, number | string>;
  transaction_count: number;
  average_transaction: number | string;
}

export interface SpendingChange {
  category: string;
  previous_period_avg: number | string;
  current_period_avg: number | string;
  change_percent: number;
  change_direction: string;
}

export interface Report {
  report_id: string;
  user_id: string;
  start_date: string;
  end_date: string;
  income_summary: IncomeSummary;
  expense_summary: ExpenseSummary;
  net_savings: number | string;
  savings_rate: number;
  budget_adherence?: Record<string, number> | null;
  spending_changes: SpendingChange[];
  generated_at: string;

  // Helper getters for backward compatibility (access via computed)
}

// Convenience helper to extract flat values
export function getReportSummary(report: Report) {
  return {
    total_income: parseFloat(String(report.income_summary?.total_income || 0)),
    total_expenses: parseFloat(String(report.expense_summary?.total_expenses || 0)),
    net_savings: parseFloat(String(report.net_savings || 0)),
    expense_breakdown: Object.fromEntries(
      Object.entries(report.expense_summary?.expenses_by_category || {})
        .map(([k, v]) => [k, parseFloat(String(v))])
    ),
    income_breakdown: Object.fromEntries(
      Object.entries(report.income_summary?.income_by_category || {})
        .map(([k, v]) => [k, parseFloat(String(v))])
    ),
    transaction_count: (report.income_summary?.transaction_count || 0) +
      (report.expense_summary?.transaction_count || 0),
  };
}


// API Response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  error: string;
  message: string;
  details?: Record<string, any>;
}
