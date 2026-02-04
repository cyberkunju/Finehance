/**
 * Reports Page
 * 
 * Generate and view financial reports, import/export transactions.
 */

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import type { Report } from '../types';
import './ReportsPage.css';

interface ImportResult {
  success_count: number;
  error_count: number;
  duplicate_count: number;
  imported_transactions: number;
  errors: Array<{
    row: number;
    field: string;
    value: string;
    message: string;
  }>;
}

function ReportsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'reports' | 'import' | 'export'>('reports');

  // Report state
  const [reportStartDate, setReportStartDate] = useState('');
  const [reportEndDate, setReportEndDate] = useState('');
  const [generatedReport, setGeneratedReport] = useState<Report | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Import state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [isImporting, setIsImporting] = useState(false);

  // Export state
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');
  const [exportCategory, setExportCategory] = useState('');
  const [exportType, setExportType] = useState('');

  const handleGenerateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportStartDate || !reportEndDate) {
      alert('Please select both start and end dates');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await apiClient.post<Report>(
        '/api/reports/generate',
        {
          user_id: user!.id,
          start_date: reportStartDate,
          end_date: reportEndDate,
        }
      );
      setGeneratedReport(response.data);
    } catch (error) {
      console.error('Failed to generate report:', error);
      alert('Failed to generate report');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExportReport = async (format: 'pdf' | 'csv') => {
    if (!generatedReport) return;

    try {
      const response = await apiClient.get(
        `/api/reports/export`,
        {
          params: {
            user_id: user!.id,
            period_start: reportStartDate,
            period_end: reportEndDate,
            format,
          },
          responseType: 'blob',
        }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `financial_report_${reportStartDate}_to_${reportEndDate}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to export report:', error);
      alert('Failed to export report');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const extension = file.name.split('.').pop()?.toLowerCase();
      if (extension !== 'csv' && extension !== 'xlsx') {
        alert('Please select a CSV or XLSX file');
        return;
      }
      setSelectedFile(file);
      setImportResult(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) {
      const extension = file.name.split('.').pop()?.toLowerCase();
      if (extension !== 'csv' && extension !== 'xlsx') {
        alert('Please select a CSV or XLSX file');
        return;
      }
      setSelectedFile(file);
      setImportResult(null);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) return;

    setIsImporting(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await apiClient.post<ImportResult>(
        '/api/import/transactions',
        formData,
        {
          params: { user_id: user!.id },
          headers: { 'Content-Type': 'multipart/form-data' },
        }
      );

      setImportResult(response.data);
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    } catch (error: any) {
      console.error('Failed to import transactions:', error);
      alert(error.response?.data?.detail || 'Failed to import transactions');
    } finally {
      setIsImporting(false);
    }
  };

  const handleDownloadTemplate = async (format: 'csv' | 'xlsx') => {
    try {
      const response = await apiClient.get(
        '/api/import/template',
        {
          params: { format },
          responseType: 'blob',
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transaction_import_template.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to download template:', error);
      alert('Failed to download template');
    }
  };

  const handleExportTransactions = async () => {
    try {
      const params: any = { user_id: user!.id };
      if (exportStartDate) params.start_date = exportStartDate;
      if (exportEndDate) params.end_date = exportEndDate;
      if (exportCategory) params.category = exportCategory;
      if (exportType) params.transaction_type = exportType;

      const response = await apiClient.get(
        '/api/export/transactions',
        {
          params,
          responseType: 'blob',
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transactions_export_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to export transactions:', error);
      alert('Failed to export transactions');
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Reports & Data</h1>
          <p>Analyze your finances and manage your data</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === 'reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          Generate Reports
        </button>
        <button
          className={`tab ${activeTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveTab('import')}
        >
          Import Transactions
        </button>
        <button
          className={`tab ${activeTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveTab('export')}
        >
          Export Transactions
        </button>
      </div>

      {/* Reports Tab */}
      {activeTab === 'reports' && (
        <div className="tab-content">
          <div className="report-generator">
            <h2>Generate Financial Report</h2>
            <form onSubmit={handleGenerateReport}>
              <div className="form-row">
                <div className="form-group">
                  <label>Start Date</label>
                  <input
                    type="date"
                    value={reportStartDate}
                    onChange={(e) => setReportStartDate(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>End Date</label>
                  <input
                    type="date"
                    value={reportEndDate}
                    onChange={(e) => setReportEndDate(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn-primary" disabled={isGenerating}>
                  {isGenerating ? 'Generating...' : 'Generate Report'}
                </button>
              </div>
            </form>

            {generatedReport && (
              <div className="report-display">
                <div className="report-header">
                  <h3>Financial Report</h3>
                  <div className="report-actions">
                    <button className="btn-secondary" onClick={() => handleExportReport('pdf')}>
                      Export PDF
                    </button>
                    <button className="btn-secondary" onClick={() => handleExportReport('csv')}>
                      Export CSV
                    </button>
                  </div>
                </div>

                <div className="report-period">
                  {new Date(generatedReport.start_date).toLocaleDateString()} - {new Date(generatedReport.end_date).toLocaleDateString()}
                </div>

                <div className="report-summary">
                  <div className="summary-card">
                    <label>Total Income</label>
                    <span className="amount positive">${parseFloat(String(generatedReport.income_summary?.total_income || 0)).toFixed(2)}</span>
                  </div>
                  <div className="summary-card">
                    <label>Total Expenses</label>
                    <span className="amount negative">${parseFloat(String(generatedReport.expense_summary?.total_expenses || 0)).toFixed(2)}</span>
                  </div>
                  <div className="summary-card">
                    <label>Net Savings</label>
                    <span className={`amount ${parseFloat(String(generatedReport.net_savings || 0)) >= 0 ? 'positive' : 'negative'}`}>
                      ${parseFloat(String(generatedReport.net_savings || 0)).toFixed(2)}
                    </span>
                  </div>
                  <div className="summary-card">
                    <label>Savings Rate</label>
                    <span className="amount">{(generatedReport.savings_rate || 0).toFixed(1)}%</span>
                  </div>
                </div>

                <div className="report-section">
                  <h4>Expense Breakdown</h4>
                  <div className="breakdown-list">
                    {Object.entries(generatedReport.expense_summary?.expenses_by_category || {}).map(([category, amount]) => (
                      <div key={category} className="breakdown-item">
                        <span className="category">{category}</span>
                        <span className="amount">${parseFloat(String(amount)).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {Object.keys(generatedReport.income_summary?.income_by_category || {}).length > 0 && (
                  <div className="report-section">
                    <h4>Income Breakdown</h4>
                    <div className="breakdown-list">
                      {Object.entries(generatedReport.income_summary?.income_by_category || {}).map(([category, amount]) => (
                        <div key={category} className="breakdown-item">
                          <span className="category">{category}</span>
                          <span className="amount">${parseFloat(String(amount)).toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="report-stats">
                  <p><strong>Total Transactions:</strong> {(generatedReport.income_summary?.transaction_count || 0) + (generatedReport.expense_summary?.transaction_count || 0)}</p>
                  <p><strong>Average Expense:</strong> ${parseFloat(String(generatedReport.expense_summary?.average_transaction || 0)).toFixed(2)}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Import Tab */}
      {activeTab === 'import' && (
        <div className="tab-content">
          <div className="import-section">
            <h2>Import Transactions</h2>
            <p className="section-description">
              Upload a CSV or XLSX file to import your transactions. The file should contain columns for date, amount, description, and optionally category and type.
            </p>

            <div className="template-download">
              <p>Don't have a file? Download a template:</p>
              <div className="template-buttons">
                <button className="btn-secondary" onClick={() => handleDownloadTemplate('csv')}>
                  Download CSV Template
                </button>
                <button className="btn-secondary" onClick={() => handleDownloadTemplate('xlsx')}>
                  Download XLSX Template
                </button>
              </div>
            </div>

            <div
              className={`file-drop-zone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <input
                id="file-input"
                type="file"
                accept=".csv,.xlsx"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              {selectedFile ? (
                <div className="file-selected">
                  <span className="file-icon">📄</span>
                  <span className="file-name">{selectedFile.name}</span>
                  <span className="file-size">({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                </div>
              ) : (
                <div className="drop-zone-content">
                  <span className="upload-icon">📁</span>
                  <p>Drag and drop your file here</p>
                  <p className="or-text">or</p>
                  <button type="button" className="btn-secondary">
                    Browse Files
                  </button>
                  <p className="file-types">Supported: CSV, XLSX</p>
                </div>
              )}
            </div>

            {selectedFile && (
              <div className="import-actions">
                <button className="btn-secondary" onClick={() => setSelectedFile(null)}>
                  Clear
                </button>
                <button className="btn-primary" onClick={handleImport} disabled={isImporting}>
                  {isImporting ? 'Importing...' : 'Import Transactions'}
                </button>
              </div>
            )}

            {importResult && (
              <div className="import-result">
                <h3>Import Results</h3>
                <div className="result-summary">
                  <div className="result-stat success">
                    <label>Successfully Imported</label>
                    <span>{importResult.success_count}</span>
                  </div>
                  <div className="result-stat duplicate">
                    <label>Duplicates Skipped</label>
                    <span>{importResult.duplicate_count}</span>
                  </div>
                  <div className="result-stat error">
                    <label>Errors</label>
                    <span>{importResult.error_count}</span>
                  </div>
                </div>

                {importResult.errors.length > 0 && (
                  <div className="error-list">
                    <h4>Errors</h4>
                    {importResult.errors.map((error, idx) => (
                      <div key={idx} className="error-item">
                        <strong>Row {error.row}:</strong> {error.message}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Export Tab */}
      {activeTab === 'export' && (
        <div className="tab-content">
          <div className="export-section">
            <h2>Export Transactions</h2>
            <p className="section-description">
              Export your transactions to CSV format. You can filter by date range, category, or transaction type.
            </p>

            <div className="export-filters">
              <div className="form-row">
                <div className="form-group">
                  <label>Start Date (Optional)</label>
                  <input
                    type="date"
                    value={exportStartDate}
                    onChange={(e) => setExportStartDate(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>End Date (Optional)</label>
                  <input
                    type="date"
                    value={exportEndDate}
                    onChange={(e) => setExportEndDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Category (Optional)</label>
                  <input
                    type="text"
                    value={exportCategory}
                    onChange={(e) => setExportCategory(e.target.value)}
                    placeholder="e.g., Groceries"
                  />
                </div>
                <div className="form-group">
                  <label>Type (Optional)</label>
                  <select value={exportType} onChange={(e) => setExportType(e.target.value)}>
                    <option value="">All</option>
                    <option value="INCOME">Income</option>
                    <option value="EXPENSE">Expense</option>
                  </select>
                </div>
              </div>

              <button className="btn-primary" onClick={handleExportTransactions}>
                Export to CSV
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ReportsPage;
