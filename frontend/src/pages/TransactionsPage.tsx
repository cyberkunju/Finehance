/**
 * Transactions Page
 * 
 * View and manage financial transactions.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { 
  getTransactions, 
  createTransaction, 
  updateTransaction, 
  deleteTransaction 
} from '../api/transactions';
import type { Transaction, TransactionCreate, TransactionType } from '../types';
import './TransactionsPage.css';

function TransactionsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  
  // State for filters
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<TransactionType | ''>('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  // State for modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  
  // State for form
  const [formData, setFormData] = useState<TransactionCreate>({
    amount: 0,
    date: new Date().toISOString().split('T')[0],
    description: '',
    type: 'EXPENSE',
    category: '',
  });
  
  // Fetch transactions
  const { data: transactionsData, isLoading, error } = useQuery({
    queryKey: ['transactions', user?.id, searchTerm, categoryFilter, typeFilter, startDate, endDate],
    queryFn: () => getTransactions(user!.id, {
      search: searchTerm || undefined,
      category: categoryFilter || undefined,
      type: typeFilter || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    }),
    enabled: !!user,
  });
  
  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: TransactionCreate) => createTransaction(user!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-report'] });
      closeModal();
    },
  });
  
  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<TransactionCreate> }) =>
      updateTransaction(id, user!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-report'] });
      closeModal();
    },
  });
  
  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTransaction(id, user!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-report'] });
    },
  });
  
  // Handlers
  const openCreateModal = () => {
    setEditingTransaction(null);
    setFormData({
      amount: 0,
      date: new Date().toISOString().split('T')[0],
      description: '',
      type: 'EXPENSE',
      category: '',
    });
    setIsModalOpen(true);
  };
  
  const openEditModal = (transaction: Transaction) => {
    setEditingTransaction(transaction);
    setFormData({
      amount: transaction.amount,
      date: transaction.date,
      description: transaction.description,
      type: transaction.type,
      category: transaction.category,
    });
    setIsModalOpen(true);
  };
  
  const closeModal = () => {
    setIsModalOpen(false);
    setEditingTransaction(null);
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (editingTransaction) {
      updateMutation.mutate({ id: editingTransaction.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };
  
  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this transaction?')) {
      deleteMutation.mutate(id);
    }
  };
  
  const clearFilters = () => {
    setSearchTerm('');
    setCategoryFilter('');
    setTypeFilter('');
    setStartDate('');
    setEndDate('');
  };
  
  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };
  
  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };
  
  if (isLoading) {
    return (
      <div className="transactions-page">
        <h1>Transactions</h1>
        <p>Loading transactions...</p>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="transactions-page">
        <h1>Transactions</h1>
        <p className="error">Failed to load transactions. Please try again.</p>
      </div>
    );
  }
  
  const transactions = transactionsData?.items || [];
  
  return (
    <div className="transactions-page">
      <div className="page-header">
        <h1>Transactions</h1>
        <button className="btn-primary" onClick={openCreateModal}>
          + Add Transaction
        </button>
      </div>
      
      {/* Filters */}
      <div className="filters-section">
        <div className="filters-grid">
          <input
            type="text"
            placeholder="Search description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="filter-input"
          />
          
          <input
            type="text"
            placeholder="Filter by category..."
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="filter-input"
          />
          
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as TransactionType | '')}
            className="filter-select"
          >
            <option value="">All Types</option>
            <option value="INCOME">Income</option>
            <option value="EXPENSE">Expense</option>
          </select>
          
          <input
            type="date"
            placeholder="Start date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="filter-input"
          />
          
          <input
            type="date"
            placeholder="End date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="filter-input"
          />
          
          <button onClick={clearFilters} className="btn-secondary">
            Clear Filters
          </button>
        </div>
      </div>
      
      {/* Transactions List */}
      <div className="transactions-list">
        {transactions.length === 0 ? (
          <div className="empty-state">
            <p>No transactions found. Add your first transaction to get started!</p>
          </div>
        ) : (
          <div className="transactions-table">
            <div className="table-header">
              <div className="col-date">Date</div>
              <div className="col-description">Description</div>
              <div className="col-category">Category</div>
              <div className="col-type">Type</div>
              <div className="col-amount">Amount</div>
              <div className="col-actions">Actions</div>
            </div>
            
            {transactions.map((transaction: Transaction) => (
              <div key={transaction.id} className="table-row">
                <div className="col-date">{formatDate(transaction.date)}</div>
                <div className="col-description">{transaction.description}</div>
                <div className="col-category">
                  <span className="category-badge">{transaction.category}</span>
                </div>
                <div className="col-type">
                  <span className={`type-badge ${transaction.type.toLowerCase()}`}>
                    {transaction.type}
                  </span>
                </div>
                <div className={`col-amount ${transaction.type.toLowerCase()}`}>
                  {transaction.type === 'INCOME' ? '+' : '-'}
                  {formatCurrency(transaction.amount)}
                </div>
                <div className="col-actions">
                  <button
                    onClick={() => openEditModal(transaction)}
                    className="btn-icon"
                    title="Edit"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDelete(transaction.id)}
                    className="btn-icon"
                    title="Delete"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingTransaction ? 'Edit Transaction' : 'Add Transaction'}</h2>
              <button onClick={closeModal} className="btn-close">×</button>
            </div>
            
            <form onSubmit={handleSubmit} className="transaction-form">
              <div className="form-group">
                <label htmlFor="type">Type *</label>
                <select
                  id="type"
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value as TransactionType })}
                  required
                >
                  <option value="EXPENSE">Expense</option>
                  <option value="INCOME">Income</option>
                </select>
              </div>
              
              <div className="form-group">
                <label htmlFor="amount">Amount *</label>
                <input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) })}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="date">Date *</label>
                <input
                  id="date"
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="description">Description *</label>
                <input
                  id="description"
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="e.g., Grocery shopping"
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="category">Category</label>
                <input
                  id="category"
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  placeholder="e.g., Food, Transportation (optional)"
                />
                <small>Leave empty for automatic categorization</small>
              </div>
              
              <div className="form-actions">
                <button type="button" onClick={closeModal} className="btn-secondary">
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn-primary"
                  disabled={createMutation.isPending || updateMutation.isPending}
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? 'Saving...'
                    : editingTransaction
                    ? 'Update Transaction'
                    : 'Add Transaction'}
                </button>
              </div>
              
              {(createMutation.isError || updateMutation.isError) && (
                <p className="error-message">
                  Failed to save transaction. Please try again.
                </p>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default TransactionsPage;
