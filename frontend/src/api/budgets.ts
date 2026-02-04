/**
 * Budgets API Service
 * 
 * API calls for budget management.
 */

import apiClient from './client';
import type { Budget, BudgetCreate, BudgetProgress } from '../types';

/**
 * Get all budgets for a user
 */
export const getBudgets = async (userId: string, activeOnly: boolean = false): Promise<Budget[]> => {
  const response = await apiClient.get<Budget[]>('/api/budgets', {
    params: {
      user_id: userId,
      active_only: activeOnly,
    },
  });
  
  return response.data;
};

/**
 * Get a single budget by ID
 */
export const getBudget = async (budgetId: string, userId: string): Promise<Budget> => {
  const response = await apiClient.get<Budget>(`/api/budgets/${budgetId}`, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Get budget progress
 */
export const getBudgetProgress = async (
  budgetId: string,
  userId: string
): Promise<BudgetProgress> => {
  const response = await apiClient.get<BudgetProgress>(`/api/budgets/${budgetId}/progress`, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Create a new budget
 */
export const createBudget = async (userId: string, budget: BudgetCreate): Promise<Budget> => {
  const response = await apiClient.post<Budget>('/api/budgets', budget, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Update a budget
 */
export const updateBudget = async (
  budgetId: string,
  userId: string,
  updates: Partial<BudgetCreate>
): Promise<Budget> => {
  const response = await apiClient.put<Budget>(`/api/budgets/${budgetId}`, updates, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Delete a budget
 */
export const deleteBudget = async (budgetId: string, userId: string): Promise<void> => {
  await apiClient.delete(`/api/budgets/${budgetId}`, {
    params: { user_id: userId },
  });
};
