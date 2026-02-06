/**
 * Settings API Service
 */

import apiClient from './client';
import type { User } from '../types';

export interface ProfileUpdateRequest {
  first_name?: string;
  last_name?: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  emailNotifications: boolean;
  budgetAlerts: boolean;
  weeklyReports: boolean;
  currency: string;
  dateFormat: string;
}

const PREFERENCES_KEY = 'ai-finance-preferences';

// Default preferences
const defaultPreferences: UserPreferences = {
  theme: 'dark',
  emailNotifications: true,
  budgetAlerts: true,
  weeklyReports: false,
  currency: 'USD',
  dateFormat: 'MM/DD/YYYY',
};

export const settingsApi = {
  /**
   * Update user profile
   */
  updateProfile: async (data: ProfileUpdateRequest): Promise<User> => {
    const response = await apiClient.put<User>('/api/auth/profile', data);
    return response.data;
  },

  /**
   * Change password
   */
  changePassword: async (data: PasswordChangeRequest): Promise<MessageResponse> => {
    const response = await apiClient.post<MessageResponse>('/api/auth/change-password', data);
    return response.data;
  },

  /**
   * Get user preferences (stored locally)
   */
  getPreferences: (): UserPreferences => {
    try {
      const stored = localStorage.getItem(PREFERENCES_KEY);
      if (stored) {
        return { ...defaultPreferences, ...JSON.parse(stored) };
      }
    } catch (e) {
      console.error('Failed to load preferences:', e);
    }
    return defaultPreferences;
  },

  /**
   * Save user preferences (stored locally)
   */
  savePreferences: (preferences: Partial<UserPreferences>): UserPreferences => {
    const current = settingsApi.getPreferences();
    const updated = { ...current, ...preferences };
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(updated));
    return updated;
  },

  /**
   * Export user data (transactions as CSV)
   */
  exportData: async (userId: string): Promise<Blob> => {
    const response = await apiClient.get(`/api/export/transactions`, {
      params: { user_id: userId },
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Delete all user transactions
   */
  deleteAllTransactions: async (userId: string): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/api/transactions/all`, {
      params: { user_id: userId },
    });
    return response.data;
  },
};

export default settingsApi;
