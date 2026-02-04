/**
 * Transactions API Service
 */

import apiClient from './client';
import type { Transaction, TransactionCreate, TransactionFilters, PaginatedResponse } from '../types';

export const transactionsApi = {
  /**
   * Get all transactions with optional filters
   */
  list: async (filters?: TransactionFilters, page = 1, pageSize = 50): Promise<PaginatedResponse<Transaction>> => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, String(value));
        }
      });
    }
    params.append('page', String(page));
    params.append('page_size', String(pageSize));

    const response = await apiClient.get<PaginatedResponse<Transaction>>('/api/transactions', { params });
    return response.data;
  },

  /**
   * Get a single transaction by ID
   */
  get: async (id: string): Promise<Transaction> => {
    const response = await apiClient.get<Transaction>(`/api/transactions/${id}`);
    return response.data;
  },

  /**
   * Create a new transaction
   */
  create: async (data: TransactionCreate): Promise<Transaction> => {
    const response = await apiClient.post<Transaction>('/api/transactions', data);
    return response.data;
  },

  /**
   * Update an existing transaction
   */
  update: async (id: string, data: Partial<TransactionCreate>): Promise<Transaction> => {
    const response = await apiClient.put<Transaction>(`/api/transactions/${id}`, data);
    return response.data;
  },

  /**
   * Delete a transaction
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/transactions/${id}`);
  },

  /**
   * Export transactions to CSV
   */
  exportCsv: async (filters?: TransactionFilters): Promise<Blob> => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, String(value));
        }
      });
    }

    const response = await apiClient.get('/api/export/transactions', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Import transactions from file
   */
  importFile: async (file: File): Promise<{ success: number; failed: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/api/import/transactions', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

export default transactionsApi;

// Convenience exports for easier imports
export const getTransactions = async (
  userId: string,
  filters?: Partial<TransactionFilters>
): Promise<PaginatedResponse<Transaction>> => {
  const params: any = { user_id: userId };
  if (filters) {
    Object.assign(params, filters);
  }
  
  const response = await apiClient.get<PaginatedResponse<Transaction>>('/api/transactions', { params });
  return response.data;
};

export const createTransaction = async (
  userId: string,
  data: TransactionCreate
): Promise<Transaction> => {
  const response = await apiClient.post<Transaction>(
    '/api/transactions',
    data,
    { params: { user_id: userId } }
  );
  return response.data;
};

export const updateTransaction = async (
  id: string,
  userId: string,
  data: Partial<TransactionCreate>
): Promise<Transaction> => {
  const response = await apiClient.put<Transaction>(
    `/api/transactions/${id}`,
    data,
    { params: { user_id: userId } }
  );
  return response.data;
};

export const deleteTransaction = async (id: string, userId: string): Promise<void> => {
  await apiClient.delete(`/api/transactions/${id}`, {
    params: { user_id: userId },
  });
};
