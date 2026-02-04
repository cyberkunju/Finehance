/**
 * Advice API Service
 * 
 * API calls for personalized financial advice.
 */

import apiClient from './client';
import type { Advice } from '../types';

/**
 * Get personalized advice for dashboard
 */
export const getPersonalizedAdvice = async (
  userId: string,
  maxRecommendations: number = 3
): Promise<Advice[]> => {
  const response = await apiClient.get<Advice[]>('/api/advice', {
    params: {
      user_id: userId,
      max_recommendations: maxRecommendations,
    },
  });
  
  return response.data;
};

/**
 * Get spending alerts
 */
export const getSpendingAlerts = async (userId: string): Promise<Advice[]> => {
  const response = await apiClient.get<Advice[]>('/api/advice/spending-alerts', {
    params: { user_id: userId },
  });
  
  return response.data;
};

/**
 * Get savings opportunities
 */
export const getSavingsOpportunities = async (
  userId: string,
  lookbackMonths: number = 3
): Promise<Advice[]> => {
  const response = await apiClient.get<Advice[]>('/api/advice/savings-opportunities', {
    params: {
      user_id: userId,
      lookback_months: lookbackMonths,
    },
  });
  
  return response.data;
};
