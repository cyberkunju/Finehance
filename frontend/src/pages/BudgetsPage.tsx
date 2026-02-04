/**
 * Budgets Page
 * 
 * Create and manage budgets, view progress, and get optimization suggestions.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { getBudgets, createBudget, deleteBudget } from '../api/budgets';
import apiClient from '../api/client';
import type { Budget, BudgetCreate } from '../types';
import './BudgetsPage.css';

interface BudgetProgressData {
  progress: Record<string, CategoryProgress>;
  alerts: BudgetAlert[];
}

interface CategoryProgress {
  category: string;
  allocated: number;
  spent: number;
  remaining: number;
  percent_used: number;
  status: string;
}

interface BudgetAlert {
  category: string;
  allocated: number;
  spent: number;
  percent_over: number;
  severity: string;
  message: string;
}

interface OptimizationSuggestion {
  category: string;
  current_allocation: number;
  suggested_allocation: number;
  change_amount: number;
  change_percent: number;
  reason: string;
  priority: string;
}

function BudgetsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [activeOnly, setActiveOnly] = useState(true);
  const [selectedBudget, setSelectedBudget] = useState<Budget | null>(null);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [showOptimizationModal, setShowOptimizationModal] = useState(false);
  const [optimizations, setOptimizations] = useState<OptimizationSuggestion[]>([]);

  // Form state
  const [formData, setFormData] = useState<BudgetCreate>({
    name: '',
    period_start: '',
    period_end: '',
    allocations: {},
  });
  const [categoryInput, setCategoryInput] = useState('');
  const [amountInput, setAmountInput] = useState('');

  // Fetch budgets
  const { data: budgets = [], isLoading } = useQuery({
    queryKey: ['budgets', user?.id, activeOnly],
    queryFn: () => getBudgets(user!.id, activeOnly),
    enabled: !!user,
  });

  // Fetch budget progress
  const { data: progressData } = useQuery({
    queryKey: ['budget-progress', selectedBudget?.id, user?.id],
    queryFn: () => apiClient.get<BudgetProgressData>(`/api/budgets/${selectedBudget!.id}/progress`, {
      params: { user_id: user!.id },
    }).then(res => res.data),
    enabled: !!selectedBudget && !!user && showProgressModal,
  });

  // Create budget mutation
  const createMutation = useMutation({
    mutationFn: (budget: BudgetCreate) => createBudget(user!.id, budget),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      setShowCreateModal(false);
      resetForm();
    },
  });

  // Delete budget mutation
  const deleteMutation = useMutation({
    mutationFn: (budgetId: string) => deleteBudget(budgetId, user!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      period_start: '',
      period_end: '',
      allocations: {},
    });
    setCategoryInput('');
    setAmountInput('');
  };

  const handleAddCategory = () => {
    if (categoryInput && amountInput && parseFloat(amountInput) > 0) {
      setFormData({
        ...formData,
        allocations: {
          ...formData.allocations,
          [categoryInput]: parseFloat(amountInput),
        },
      });
      setCategoryInput('');
      setAmountInput('');
    }
  };

  const handleRemoveCategory = (category: string) => {
    const newAllocations = { ...formData.allocations };
    delete newAllocations[category];
    setFormData({ ...formData, allocations: newAllocations });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (Object.keys(formData.allocations).length === 0) {
      alert('Please add at least one category allocation');
      return;
    }
    createMutation.mutate(formData);
  };

  const handleDelete = (budgetId: string) => {
    if (window.confirm('Are you sure you want to delete this budget?')) {
      deleteMutation.mutate(budgetId);
    }
  };

  const handleViewProgress = (budget: Budget) => {
    setSelectedBudget(budget);
    setShowProgressModal(true);
  };

  const handleGetOptimizations = async (budget: Budget) => {
    try {
      const response = await apiClient.post<{ suggestions: OptimizationSuggestion[] }>(
        `/api/budgets/${budget.id}/optimize`,
        {},
        { params: { user_id: user!.id, historical_months: 3 } }
      );
      setOptimizations(response.data.suggestions);
      setSelectedBudget(budget);
      setShowOptimizationModal(true);
    } catch (error) {
      console.error('Failed to get optimizations:', error);
      alert('Failed to get optimization suggestions');
    }
  };

  const handleApplyOptimizations = async () => {
    if (!selectedBudget) return;
    
    try {
      await apiClient.put(
        `/api/budgets/${selectedBudget.id}/apply-optimization`,
        {
          suggestions: optimizations,
          user_approved: true,
        },
        { params: { user_id: user!.id } }
      );
      
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      setShowOptimizationModal(false);
      alert('Optimizations applied successfully!');
    } catch (error) {
      console.error('Failed to apply optimizations:', error);
      alert('Failed to apply optimizations');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'ok':
      case 'good':
        return '#10b981';
      case 'warning':
        return '#f59e0b';
      case 'exceeded':
      case 'over':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority.toUpperCase()) {
      case 'CRITICAL':
        return '#ef4444';
      case 'HIGH':
        return '#f59e0b';
      case 'MEDIUM':
        return '#3b82f6';
      case 'LOW':
        return '#6b7280';
      default:
        return '#6b7280';
    }
  };

  if (isLoading) {
    return <div className="page"><p>Loading budgets...</p></div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Budgets</h1>
          <p>Plan and track your spending</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          Create Budget
        </button>
      </div>

      <div className="filter-bar">
        <label>
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)}
          />
          Show active budgets only
        </label>
      </div>

      {budgets.length === 0 ? (
        <div className="empty-state">
          <p>No budgets found. Create your first budget to start tracking spending!</p>
        </div>
      ) : (
        <div className="budgets-grid">
          {budgets.map((budget) => (
            <div key={budget.id} className="budget-card">
              <div className="budget-header">
                <h3>{budget.name}</h3>
                <button
                  className="btn-delete"
                  onClick={() => handleDelete(budget.id)}
                  title="Delete budget"
                >
                  ×
                </button>
              </div>
              <div className="budget-period">
                {new Date(budget.period_start).toLocaleDateString()} - {new Date(budget.period_end).toLocaleDateString()}
              </div>
              <div className="budget-categories">
                <strong>Categories:</strong>
                <ul>
                  {Object.entries(budget.allocations).map(([category, amount]) => (
                    <li key={category}>
                      {category}: ${amount.toFixed(2)}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="budget-total">
                <strong>Total Budget:</strong> ${Object.values(budget.allocations).reduce((sum, val) => sum + val, 0).toFixed(2)}
              </div>
              <div className="budget-actions">
                <button className="btn-secondary" onClick={() => handleViewProgress(budget)}>
                  View Progress
                </button>
                <button className="btn-secondary" onClick={() => handleGetOptimizations(budget)}>
                  Optimize
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Budget Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create Budget</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Budget Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Start Date</label>
                  <input
                    type="date"
                    value={formData.period_start}
                    onChange={(e) => setFormData({ ...formData, period_start: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>End Date</label>
                  <input
                    type="date"
                    value={formData.period_end}
                    onChange={(e) => setFormData({ ...formData, period_end: e.target.value })}
                    required
                  />
                </div>
              </div>
              
              <div className="form-section">
                <h3>Category Allocations</h3>
                <div className="form-row">
                  <div className="form-group">
                    <label>Category</label>
                    <input
                      type="text"
                      value={categoryInput}
                      onChange={(e) => setCategoryInput(e.target.value)}
                      placeholder="e.g., Groceries"
                    />
                  </div>
                  <div className="form-group">
                    <label>Amount</label>
                    <input
                      type="number"
                      step="0.01"
                      value={amountInput}
                      onChange={(e) => setAmountInput(e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleAddCategory}
                    style={{ marginTop: '24px' }}
                  >
                    Add
                  </button>
                </div>
                
                {Object.keys(formData.allocations).length > 0 && (
                  <div className="allocations-list">
                    {Object.entries(formData.allocations).map(([category, amount]) => (
                      <div key={category} className="allocation-item">
                        <span>{category}: ${amount.toFixed(2)}</span>
                        <button
                          type="button"
                          className="btn-delete-small"
                          onClick={() => handleRemoveCategory(category)}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating...' : 'Create Budget'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Progress Modal */}
      {showProgressModal && selectedBudget && (
        <div className="modal-overlay" onClick={() => setShowProgressModal(false)}>
          <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedBudget.name} - Progress</h2>
              <button className="modal-close" onClick={() => setShowProgressModal(false)}>×</button>
            </div>
            
            {progressData && (
              <div className="progress-content">
                {/* Alerts */}
                {progressData.alerts && progressData.alerts.length > 0 && (
                  <div className="alerts-section">
                    <h3>Alerts</h3>
                    {progressData.alerts.map((alert, idx) => (
                      <div key={idx} className="alert" style={{ borderLeftColor: alert.severity === 'high' ? '#ef4444' : '#f59e0b' }}>
                        <strong>{alert.category}</strong>
                        <p>{alert.message}</p>
                        <small>Over budget by {alert.percent_over.toFixed(1)}%</small>
                      </div>
                    ))}
                  </div>
                )}

                {/* Progress by Category */}
                <div className="progress-section">
                  <h3>Category Progress</h3>
                  {Object.entries(progressData.progress).map(([category, progress]) => (
                    <div key={category} className="progress-item">
                      <div className="progress-header">
                        <span className="category-name">{progress.category}</span>
                        <span className="progress-amounts">
                          ${progress.spent.toFixed(2)} / ${progress.allocated.toFixed(2)}
                        </span>
                      </div>
                      <div className="progress-bar-container">
                        <div
                          className="progress-bar"
                          style={{
                            width: `${Math.min(progress.percent_used, 100)}%`,
                            backgroundColor: getStatusColor(progress.status),
                          }}
                        />
                      </div>
                      <div className="progress-footer">
                        <span style={{ color: getStatusColor(progress.status) }}>
                          {progress.percent_used.toFixed(1)}% used
                        </span>
                        <span>
                          ${progress.remaining.toFixed(2)} remaining
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Optimization Modal */}
      {showOptimizationModal && selectedBudget && (
        <div className="modal-overlay" onClick={() => setShowOptimizationModal(false)}>
          <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedBudget.name} - Optimization Suggestions</h2>
              <button className="modal-close" onClick={() => setShowOptimizationModal(false)}>×</button>
            </div>
            
            {optimizations.length === 0 ? (
              <div className="empty-state">
                <p>No optimization suggestions available. Your budget looks good!</p>
              </div>
            ) : (
              <div className="optimizations-content">
                <p className="optimization-intro">
                  Based on your spending patterns over the last 3 months, here are some suggestions to optimize your budget:
                </p>
                
                {optimizations.map((suggestion, idx) => (
                  <div key={idx} className="optimization-card" style={{ borderLeftColor: getPriorityColor(suggestion.priority) }}>
                    <div className="optimization-header">
                      <h4>{suggestion.category}</h4>
                      <span className="priority-badge" style={{ backgroundColor: getPriorityColor(suggestion.priority) }}>
                        {suggestion.priority}
                      </span>
                    </div>
                    <div className="optimization-amounts">
                      <div>
                        <label>Current:</label>
                        <span>${suggestion.current_allocation.toFixed(2)}</span>
                      </div>
                      <div className="arrow">→</div>
                      <div>
                        <label>Suggested:</label>
                        <span>${suggestion.suggested_allocation.toFixed(2)}</span>
                      </div>
                      <div className={suggestion.change_amount > 0 ? 'change-positive' : 'change-negative'}>
                        {suggestion.change_amount > 0 ? '+' : ''}${suggestion.change_amount.toFixed(2)}
                        ({suggestion.change_percent > 0 ? '+' : ''}{suggestion.change_percent.toFixed(1)}%)
                      </div>
                    </div>
                    <p className="optimization-reason">{suggestion.reason}</p>
                  </div>
                ))}

                <div className="modal-actions">
                  <button className="btn-secondary" onClick={() => setShowOptimizationModal(false)}>
                    Cancel
                  </button>
                  <button className="btn-primary" onClick={handleApplyOptimizations}>
                    Apply All Suggestions
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default BudgetsPage;
