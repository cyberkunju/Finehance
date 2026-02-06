/**
 * Goals Page
 *
 * Set and track financial goals.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, X, Trash2, Trophy, AlertTriangle, CheckCircle, Clock, Eye } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { usePreferences } from '../contexts/PreferencesContext';
import { getGoals, createGoal, updateGoalProgress, deleteGoal } from '../api/goals';
import apiClient from '../api/client';
import type { FinancialGoal, GoalCreate } from '../types';
import './GoalsPage.css';

interface GoalProgressData {
  goal_id: string;
  name: string;
  target_amount: number;
  current_amount: number;
  progress_percent: number;
  remaining_amount: number;
  days_remaining: number | null;
  estimated_completion_date: string | null;
  is_at_risk: boolean;
  risk_reason: string | null;
}

interface GoalRiskAlert {
  goal_id: string;
  name: string;
  severity: string;
  message: string;
  recommended_action: string;
}

function GoalsPage() {
  const { user } = useAuth();
  const { formatCurrency, formatDate } = usePreferences();
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState<FinancialGoal | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ACTIVE');
  const [showCelebration, setShowCelebration] = useState(false);
  const [celebrationGoal, setCelebrationGoal] = useState<string>('');

  // Form state
  const [formData, setFormData] = useState<GoalCreate>({
    name: '',
    target_amount: 0,
    deadline: undefined,
    category: undefined,
    current_amount: 0,
  });
  const [progressAmount, setProgressAmount] = useState('');

  // Fetch goals
  const { data: goals = [], isLoading } = useQuery({
    queryKey: ['goals', user?.id, statusFilter],
    queryFn: () => getGoals(user!.id, statusFilter),
    enabled: !!user,
  });

  // Fetch risk alerts
  const { data: riskAlerts = [] } = useQuery({
    queryKey: ['goal-risks', user?.id],
    queryFn: () => apiClient.get<GoalRiskAlert[]>('/api/goals/risks/alerts', {
      params: { user_id: user!.id },
    }).then(res => res.data),
    enabled: !!user && statusFilter === 'ACTIVE',
  });

  // Fetch goal progress
  const { data: progressData } = useQuery({
    queryKey: ['goal-progress', selectedGoal?.id, user?.id],
    queryFn: () => apiClient.get<GoalProgressData>(`/api/goals/${selectedGoal!.id}/progress`, {
      params: { user_id: user!.id },
    }).then(res => res.data),
    enabled: !!selectedGoal && !!user && showProgressModal,
  });

  // Create goal mutation
  const createMutation = useMutation({
    mutationFn: (goal: GoalCreate) => createGoal(user!.id, goal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      setShowCreateModal(false);
      resetForm();
    },
  });

  // Update progress mutation
  const updateProgressMutation = useMutation({
    mutationFn: ({ goalId, amount }: { goalId: string; amount: number }) =>
      updateGoalProgress(goalId, user!.id, amount),
    onSuccess: (updatedGoal) => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['goal-progress'] });
      setProgressAmount('');

      // Check if goal is achieved
      if (updatedGoal.current_amount >= updatedGoal.target_amount) {
        setCelebrationGoal(updatedGoal.name);
        setShowCelebration(true);
        setTimeout(() => setShowCelebration(false), 5000);
      }
    },
  });

  // Delete goal mutation
  const deleteMutation = useMutation({
    mutationFn: (goalId: string) => deleteGoal(goalId, user!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      target_amount: 0,
      deadline: undefined,
      category: undefined,
      current_amount: 0,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.target_amount <= 0) {
      alert('Target amount must be greater than 0');
      return;
    }
    createMutation.mutate(formData);
  };

  const handleDelete = (goalId: string) => {
    if (window.confirm('Are you sure you want to delete this goal?')) {
      deleteMutation.mutate(goalId);
    }
  };

  const handleViewProgress = (goal: FinancialGoal) => {
    setSelectedGoal(goal);
    setShowProgressModal(true);
  };

  const handleUpdateProgress = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGoal || !progressAmount) return;

    const amount = parseFloat(progressAmount);
    if (amount <= 0) {
      alert('Amount must be greater than 0');
      return;
    }

    updateProgressMutation.mutate({ goalId: selectedGoal.id, amount });
  };

  const getProgressColor = (percent: number) => {
    if (percent >= 100) return 'var(--color-success)';
    if (percent >= 75) return 'var(--color-text-primary)';
    if (percent >= 50) return 'var(--color-text-muted)';
    return 'var(--color-text-tertiary)';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'var(--color-danger)';
      case 'high':
        return 'var(--color-warning)';
      case 'medium':
        return 'var(--color-text-muted)';
      default:
        return 'var(--color-text-tertiary)';
    }
  };

  // Precompute progress data values for display
  const progCurrent = progressData ? parseFloat(String(progressData.current_amount || 0)) : 0;
  const progTarget = progressData ? parseFloat(String(progressData.target_amount || 0)) : 0;
  const progRemaining = progressData ? parseFloat(String(progressData.remaining_amount || 0)) : 0;
  const progPercent = progressData?.progress_percent || 0;

  if (isLoading) {
    return <div className="page"><p>Loading goals...</p></div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Financial Goals</h1>
          <p>Set and achieve your financial objectives</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={16} strokeWidth={2} />
          Create Goal
        </button>
      </div>

      {/* Celebration Banner */}
      {showCelebration && (
        <div className="celebration-banner">
          <div className="celebration-content">
            <Trophy size={32} strokeWidth={1.5} />
            <div>
              <strong>Congratulations!</strong>
              <p>You've achieved your goal: {celebrationGoal}!</p>
            </div>
          </div>
        </div>
      )}

      {/* Risk Alerts */}
      {riskAlerts.length > 0 && (
        <div className="alerts-section">
          <h3 className="alerts-heading">
            <AlertTriangle size={16} strokeWidth={1.5} />
            Goal Risk Alerts
          </h3>
          {riskAlerts.map((alert) => (
            <div key={alert.goal_id} className="risk-alert" style={{ borderLeftColor: getSeverityColor(alert.severity) }}>
              <div className="alert-header">
                <strong>{alert.name}</strong>
                <span className="severity-badge" style={{ backgroundColor: getSeverityColor(alert.severity) }}>
                  {alert.severity}
                </span>
              </div>
              <p>{alert.message}</p>
              <p className="recommended-action">
                <strong>Recommended:</strong> {alert.recommended_action}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Status Filter */}
      <div className="filter-bar">
        <label>Status:</label>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All</option>
          <option value="ACTIVE">Active</option>
          <option value="ACHIEVED">Achieved</option>
          <option value="ARCHIVED">Archived</option>
        </select>
      </div>

      {goals.length === 0 ? (
        <div className="empty-state">
          <p>No goals found. Create your first goal to start tracking progress!</p>
        </div>
      ) : (
        <div className="goals-grid">
          {goals.map((goal) => {
            const currentAmount = parseFloat(String(goal.current_amount || 0));
            const targetAmount = parseFloat(String(goal.target_amount || 1));
            const progress = (currentAmount / targetAmount) * 100;
            const isAchieved = goal.status === 'ACHIEVED';

            return (
              <div key={goal.id} className={`goal-card ${isAchieved ? 'achieved' : ''}`}>
                <div className="goal-header">
                  <h3>{goal.name}</h3>
                  <button
                    className="btn-icon"
                    onClick={() => handleDelete(goal.id)}
                    title="Delete goal"
                  >
                    <Trash2 size={16} strokeWidth={1.5} />
                  </button>
                </div>

                {goal.category && (
                  <div className="goal-category">{goal.category}</div>
                )}

                <div className="goal-amounts">
                  <div>
                    <label>Current</label>
                    <span className="amount">{formatCurrency(currentAmount)}</span>
                  </div>
                  <div>
                    <label>Target</label>
                    <span className="amount">{formatCurrency(targetAmount)}</span>
                  </div>
                </div>

                <div className="progress-bar-container">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${Math.min(progress, 100)}%`,
                      backgroundColor: getProgressColor(progress),
                    }}
                  />
                </div>
                <div className="progress-text">
                  {progress.toFixed(1)}% Complete
                </div>

                {goal.deadline && (
                  <div className="goal-deadline">
                    <Clock size={12} strokeWidth={1.5} />
                    {formatDate(goal.deadline)}
                  </div>
                )}

                {isAchieved && (
                  <div className="achievement-badge">
                    <CheckCircle size={14} strokeWidth={2} />
                    Achieved
                  </div>
                )}

                <div className="goal-actions">
                  <button className="btn-secondary" onClick={() => handleViewProgress(goal)}>
                    <Eye size={14} strokeWidth={1.5} />
                    View Details
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Goal Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create Financial Goal</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>
                <X size={20} strokeWidth={1.5} />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Goal Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Emergency Fund"
                  required
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Target Amount *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.target_amount || ''}
                    onChange={(e) => setFormData({ ...formData, target_amount: parseFloat(e.target.value) || 0 })}
                    placeholder="0.00"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Starting Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.current_amount || ''}
                    onChange={(e) => setFormData({ ...formData, current_amount: parseFloat(e.target.value) || 0 })}
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Category</label>
                  <input
                    type="text"
                    value={formData.category || ''}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value || undefined })}
                    placeholder="e.g., Savings"
                  />
                </div>
                <div className="form-group">
                  <label>Deadline</label>
                  <input
                    type="date"
                    value={formData.deadline || ''}
                    onChange={(e) => setFormData({ ...formData, deadline: e.target.value || undefined })}
                  />
                </div>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating...' : 'Create Goal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Progress Modal */}
      {showProgressModal && selectedGoal && (
        <div className="modal-overlay" onClick={() => setShowProgressModal(false)}>
          <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedGoal.name} — Progress</h2>
              <button className="modal-close" onClick={() => setShowProgressModal(false)}>
                <X size={20} strokeWidth={1.5} />
              </button>
            </div>

            {progressData && (
              <div className="progress-details">
                <div className="progress-stats">
                  <div className="stat-card">
                    <label>Current Amount</label>
                    <span className="stat-value">{formatCurrency(progCurrent)}</span>
                  </div>
                  <div className="stat-card">
                    <label>Target Amount</label>
                    <span className="stat-value">{formatCurrency(progTarget)}</span>
                  </div>
                  <div className="stat-card">
                    <label>Remaining</label>
                    <span className="stat-value">{formatCurrency(progRemaining)}</span>
                  </div>
                  <div className="stat-card">
                    <label>Progress</label>
                    <span className="stat-value" style={{ color: getProgressColor(progPercent) }}>
                      {progPercent.toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="progress-bar-container large">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${Math.min(progPercent, 100)}%`,
                      backgroundColor: getProgressColor(progPercent),
                    }}
                  />
                </div>

                {progressData.days_remaining !== null && (
                  <div className="timeline-info">
                    <p>
                      <strong>Days Remaining:</strong> {progressData.days_remaining} days
                    </p>
                    {progressData.estimated_completion_date && (
                      <p>
                        <strong>Estimated Completion:</strong>{' '}
                        {formatDate(progressData.estimated_completion_date)}
                      </p>
                    )}
                  </div>
                )}

                {progressData.is_at_risk && progressData.risk_reason && (
                  <div className="risk-warning">
                    <div className="risk-warning-header">
                      <AlertTriangle size={16} strokeWidth={1.5} />
                      <strong>At Risk</strong>
                    </div>
                    <p>{progressData.risk_reason}</p>
                  </div>
                )}

                <form onSubmit={handleUpdateProgress} className="progress-update-form">
                  <h3>Add Progress</h3>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Amount to Add</label>
                      <input
                        type="number"
                        step="0.01"
                        value={progressAmount}
                        onChange={(e) => setProgressAmount(e.target.value)}
                        placeholder="0.00"
                      />
                    </div>
                    <button
                      type="submit"
                      className="btn-primary"
                      disabled={updateProgressMutation.isPending}
                      style={{ marginTop: '24px' }}
                    >
                      {updateProgressMutation.isPending ? 'Updating...' : 'Add Progress'}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default GoalsPage;
