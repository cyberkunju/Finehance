/**
 * Goals API Service
 * 
 * API calls for financial goal management.
 */

import apiClient from './client';
import type { FinancialGoal, GoalCreate, GoalProgress } from '../types';

/**
 * Get all goals for a user
 */
export const getGoals = async (userId: string, status?: string): Promise<FinancialGoal[]> => {
  const response = await apiClient.get<FinancialGoal[]>('/api/goals', {
    params: {
      user_id: userId,
      status,
    },
  });
  
  return response.data;
};

/**
 * Get a single goal by ID
 */
export const getGoal = async (goalId: string, userId: string): Promise<FinancialGoal> => {
  const response = await apiClient.get<FinancialGoal>(`/api/goals/${goalId}`, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Get goal progress
 */
export const getGoalProgress = async (goalId: string, userId: string): Promise<GoalProgress> => {
  const response = await apiClient.get<GoalProgress>(`/api/goals/${goalId}/progress`, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Create a new goal
 */
export const createGoal = async (userId: string, goal: GoalCreate): Promise<FinancialGoal> => {
  const response = await apiClient.post<FinancialGoal>('/api/goals', goal, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Update goal progress
 */
export const updateGoalProgress = async (
  goalId: string,
  userId: string,
  amount: number
): Promise<FinancialGoal> => {
  const response = await apiClient.post<FinancialGoal>(
    `/api/goals/${goalId}/progress`,
    { amount },
    { params: { user_id: userId } }
  );
  
  return response.data;
};

/**
 * Update a goal
 */
export const updateGoal = async (
  goalId: string,
  userId: string,
  updates: Partial<GoalCreate>
): Promise<FinancialGoal> => {
  const response = await apiClient.put<FinancialGoal>(`/api/goals/${goalId}`, updates, {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Delete a goal
 */
export const deleteGoal = async (goalId: string, userId: string): Promise<void> => {
  await apiClient.delete(`/api/goals/${goalId}`, {
    params: { user_id: userId },
  });
};
