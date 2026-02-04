# Database Schema Documentation

## Overview

This document describes the database schema for the AI Finance Platform. The schema consists of 6 main tables that support user management, transaction tracking, budgeting, financial goals, ML model management, and external API connections.

## Tables

### 1. Users Table

Stores user account information for authentication and profile management.

**Columns:**
- `id` (UUID, PK): Unique user identifier
- `email` (VARCHAR(255), UNIQUE, NOT NULL): User email address
- `password_hash` (VARCHAR(255), NOT NULL): Hashed password using bcrypt
- `first_name` (VARCHAR(100)): User's first name
- `last_name` (VARCHAR(100)): User's last name
- `created_at` (TIMESTAMP, NOT NULL): Account creation timestamp
- `updated_at` (TIMESTAMP, NOT NULL): Last update timestamp

**Indexes:**
- Primary key on `id`
- Unique index on `email`

**Relationships:**
- One-to-many with `transactions`
- One-to-many with `budgets`
- One-to-many with `financial_goals`
- One-to-many with `ml_models`
- One-to-many with `connections`

---

### 2. Transactions Table

Stores all financial transactions (income and expenses) for users.

**Columns:**
- `id` (UUID, PK): Unique transaction identifier
- `user_id` (UUID, FK, NOT NULL): Reference to users table
- `amount` (NUMERIC(12,2), NOT NULL): Transaction amount (always positive)
- `date` (DATE, NOT NULL): Transaction date
- `description` (TEXT, NOT NULL): Transaction description
- `category` (VARCHAR(50), NOT NULL): Transaction category (e.g., Groceries, Salary)
- `type` (VARCHAR(10), NOT NULL): Transaction type (INCOME or EXPENSE)
- `source` (VARCHAR(20), NOT NULL): Data source (MANUAL, API, FILE_IMPORT)
- `confidence_score` (NUMERIC(3,2)): ML categorization confidence (0-1)
- `connection_id` (UUID, FK): Reference to connections table (if from API)
- `created_at` (TIMESTAMP, NOT NULL): Record creation timestamp
- `updated_at` (TIMESTAMP, NOT NULL): Last update timestamp
- `deleted_at` (TIMESTAMP): Soft delete timestamp

**Constraints:**
- `type` must be 'INCOME' or 'EXPENSE'
- `source` must be 'MANUAL', 'API', or 'FILE_IMPORT'
- `amount` must be >= 0
- `confidence_score` must be NULL or between 0 and 1

**Indexes:**
- Primary key on `id`
- Index on `user_id`
- Index on `date`
- Index on `category`
- Composite index on `(user_id, date)` for date-range queries
- Composite index on `(user_id, category)` for category filtering
- Composite index on `(user_id, type)` for income/expense filtering
- Index on `deleted_at` for soft delete queries

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE DELETE)
- `connection_id` → `connections.id` (SET NULL on delete)

---

### 3. Budgets Table

Stores budget allocations for different spending categories.

**Columns:**
- `id` (UUID, PK): Unique budget identifier
- `user_id` (UUID, FK, NOT NULL): Reference to users table
- `name` (VARCHAR(100), NOT NULL): Budget name
- `period_start` (DATE, NOT NULL): Budget period start date
- `period_end` (DATE, NOT NULL): Budget period end date
- `allocations` (JSONB, NOT NULL): JSON object mapping categories to amounts
- `created_at` (TIMESTAMP, NOT NULL): Record creation timestamp
- `updated_at` (TIMESTAMP, NOT NULL): Last update timestamp

**Indexes:**
- Primary key on `id`
- Index on `user_id`
- Index on `period_start`
- Index on `period_end`
- Composite index on `(user_id, period_start, period_end)` for period queries

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE DELETE)

**Example allocations JSON:**
```json
{
  "Groceries": 500.00,
  "Dining": 200.00,
  "Transportation": 150.00,
  "Entertainment": 100.00
}
```

---

### 4. Financial Goals Table

Stores user financial goals and tracks progress toward them.

**Columns:**
- `id` (UUID, PK): Unique goal identifier
- `user_id` (UUID, FK, NOT NULL): Reference to users table
- `name` (VARCHAR(100), NOT NULL): Goal name
- `target_amount` (NUMERIC(12,2), NOT NULL): Target amount to achieve
- `current_amount` (NUMERIC(12,2), NOT NULL, DEFAULT 0): Current progress amount
- `deadline` (DATE): Optional goal deadline
- `category` (VARCHAR(50)): Optional linked category for auto-tracking
- `status` (VARCHAR(20), NOT NULL, DEFAULT 'ACTIVE'): Goal status
- `created_at` (TIMESTAMP, NOT NULL): Record creation timestamp
- `updated_at` (TIMESTAMP, NOT NULL): Last update timestamp

**Constraints:**
- `status` must be 'ACTIVE', 'ACHIEVED', or 'ARCHIVED'
- `target_amount` must be > 0
- `current_amount` must be >= 0

**Indexes:**
- Primary key on `id`
- Index on `user_id`
- Index on `status`
- Composite index on `(user_id, status)` for filtering active goals
- Composite index on `(user_id, deadline)` for deadline tracking

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE DELETE)

---

### 5. ML Models Table

Stores metadata about machine learning models (categorization and prediction).

**Columns:**
- `id` (UUID, PK): Unique model identifier
- `model_type` (VARCHAR(50), NOT NULL): Model type (CATEGORIZATION or PREDICTION)
- `user_id` (UUID, FK): Reference to users table (NULL for global models)
- `version` (VARCHAR(20), NOT NULL): Model version string
- `accuracy` (FLOAT): Model accuracy metric (0-1)
- `precision` (FLOAT): Model precision metric (0-1)
- `recall` (FLOAT): Model recall metric (0-1)
- `trained_at` (TIMESTAMP, NOT NULL): Model training timestamp
- `model_path` (VARCHAR(500), NOT NULL): Path to model file (S3 or filesystem)
- `is_active` (BOOLEAN, NOT NULL, DEFAULT TRUE): Whether model is currently active

**Constraints:**
- `model_type` must be 'CATEGORIZATION' or 'PREDICTION'
- `accuracy` must be NULL or between 0 and 1
- `precision` must be NULL or between 0 and 1
- `recall` must be NULL or between 0 and 1

**Indexes:**
- Primary key on `id`
- Index on `model_type`
- Index on `is_active`
- Composite index on `(model_type, is_active)` for finding active models
- Composite index on `(user_id, model_type)` for user-specific models
- Composite index on `(user_id, model_type, is_active)` for active user models

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE DELETE)

**Notes:**
- Global models have `user_id = NULL`
- User-specific models are created after sufficient training data (>50 transactions)

---

### 6. Connections Table

Stores financial API connection information (e.g., Plaid, Yodlee).

**Columns:**
- `id` (UUID, PK): Unique connection identifier
- `user_id` (UUID, FK, NOT NULL): Reference to users table
- `institution_id` (VARCHAR(100), NOT NULL): Financial institution identifier
- `institution_name` (VARCHAR(200), NOT NULL): Human-readable institution name
- `access_token` (TEXT, NOT NULL): Encrypted API access token
- `last_sync` (TIMESTAMP): Last successful sync timestamp
- `status` (VARCHAR(20), NOT NULL, DEFAULT 'ACTIVE'): Connection status
- `created_at` (TIMESTAMP, NOT NULL): Record creation timestamp

**Constraints:**
- `status` must be 'ACTIVE', 'EXPIRED', or 'ERROR'

**Indexes:**
- Primary key on `id`
- Index on `user_id`
- Index on `status`
- Composite index on `(user_id, status)` for filtering active connections
- Composite index on `(user_id, institution_id)` for institution lookup

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE DELETE)

**Security Notes:**
- `access_token` should be encrypted at rest using AES-256
- Tokens should be stored in a secure vault with restricted access

---

## Entity Relationship Diagram

```
┌─────────────┐
│    Users    │
└──────┬──────┘
       │
       ├──────────────────────────────────────┐
       │                                      │
       ▼                                      ▼
┌─────────────┐                      ┌──────────────┐
│Transactions │                      │ Connections  │
└──────┬──────┘                      └──────┬───────┘
       │                                     │
       └─────────────────────────────────────┘
       
       │
       ├──────────────┬──────────────┬──────────────┐
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐
│ Budgets  │  │Financial Goals│  │ML Models │  │          │
└──────────┘  └──────────────┘  └──────────┘  └──────────┘
```

## Query Optimization

### Common Query Patterns

1. **Get user transactions by date range:**
   - Uses index: `idx_transactions_user_date`
   ```sql
   SELECT * FROM transactions 
   WHERE user_id = ? AND date BETWEEN ? AND ?
   ORDER BY date DESC;
   ```

2. **Get transactions by category:**
   - Uses index: `idx_transactions_user_category`
   ```sql
   SELECT * FROM transactions 
   WHERE user_id = ? AND category = ?;
   ```

3. **Get active budget for current period:**
   - Uses index: `idx_budgets_user_period`
   ```sql
   SELECT * FROM budgets 
   WHERE user_id = ? 
   AND period_start <= CURRENT_DATE 
   AND period_end >= CURRENT_DATE;
   ```

4. **Get active financial goals:**
   - Uses index: `idx_financial_goals_user_status`
   ```sql
   SELECT * FROM financial_goals 
   WHERE user_id = ? AND status = 'ACTIVE';
   ```

5. **Get active ML model for user:**
   - Uses index: `idx_ml_models_user_type_active`
   ```sql
   SELECT * FROM ml_models 
   WHERE user_id = ? 
   AND model_type = 'CATEGORIZATION' 
   AND is_active = TRUE
   LIMIT 1;
   ```

## Migration

The database schema is managed using Alembic migrations. The initial schema is created by migration `001_create_initial_schema.py`.

To apply migrations:
```bash
poetry run alembic upgrade head
```

To create a new migration:
```bash
poetry run alembic revision --autogenerate -m "Description"
```

## Data Integrity

### Cascade Deletes
- When a user is deleted, all related records are automatically deleted (CASCADE)
- When a connection is deleted, related transactions have `connection_id` set to NULL (SET NULL)

### Soft Deletes
- Transactions support soft deletes via the `deleted_at` column
- Soft-deleted transactions are excluded from queries but retained for audit purposes

### Check Constraints
- Ensure data validity at the database level
- Examples: transaction types, status values, amount ranges, metric ranges

## Performance Considerations

1. **Indexes**: All foreign keys and frequently queried columns are indexed
2. **Composite Indexes**: Multi-column indexes for common query patterns
3. **JSONB**: Used for flexible budget allocations with efficient querying
4. **Partitioning**: Consider partitioning transactions table by date for large datasets
5. **Connection Pooling**: Configured in `app/database.py` with pool_size=20

## Security

1. **Encryption at Rest**: Sensitive fields (passwords, tokens) are encrypted
2. **Password Hashing**: Uses bcrypt with salt
3. **Token Storage**: API tokens encrypted before storage
4. **SQL Injection**: Protected by SQLAlchemy ORM parameterized queries
5. **Access Control**: Row-level security via user_id foreign keys

## Backup and Recovery

Recommended backup strategy:
1. **Daily full backups** of PostgreSQL database
2. **Point-in-time recovery** enabled
3. **Backup retention**: 30 days minimum
4. **Test restores**: Monthly validation

## Monitoring

Key metrics to monitor:
1. **Query performance**: Slow query log (>100ms)
2. **Connection pool**: Usage and wait times
3. **Table sizes**: Growth trends
4. **Index usage**: Unused indexes
5. **Lock contention**: Blocking queries
