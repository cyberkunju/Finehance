/**
 * Reports API Service
 * 
 * API calls for financial reports.
 */

import apiClient from './client';
import type { Report } from '../types';

export interface ReportRequest {
  user_id: string;
  start_date: string;
  end_date: string;
}

/**
 * Generate a financial report
 */
export const generateReport = async (request: ReportRequest): Promise<Report> => {
  const response = await apiClient.post<Report>('/api/reports/generate', request);
  return response.data;
};

/**
 * Export report as CSV
 */
export const exportReportCSV = async (
  userId: string,
  startDate: string,
  endDate: string
): Promise<Blob> => {
  const response = await apiClient.post(
    '/api/reports/export/csv',
    {},
    {
      params: {
        user_id: userId,
        start_date: startDate,
        end_date: endDate,
      },
      responseType: 'blob',
    }
  );
  
  return response.data;
};

/**
 * Export report as PDF
 */
export const exportReportPDF = async (
  userId: string,
  startDate: string,
  endDate: string
): Promise<Blob> => {
  const response = await apiClient.post(
    '/api/reports/export/pdf',
    {},
    {
      params: {
        user_id: userId,
        start_date: startDate,
        end_date: endDate,
      },
      responseType: 'blob',
    }
  );
  
  return response.data;
};
