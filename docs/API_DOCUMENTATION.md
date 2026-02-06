# API Documentation

## Overview

Finehance provides a RESTful API for managing personal finances, including transactions, budgets, goals, predictions, and financial advice. All endpoints require JWT authentication unless otherwise specified.

**Base URL**: `http://localhost:8000/api`  
**Swagger UI**: `http://localhost:8000/docs` (interactive, auto-generated)  
**Authentication**: JWT Bearer Token (HS256)  
**Content-Type**: `application/json`

## Table of Contents

1. [Authentication](#authentication)
2. [Transactions](#transactions)
3. [Budgets](#budgets)
4. [Goals](#goals)
5. [Predictions](#predictions)
6. [Advice](#advice)
7. [Reports](#reports)
8. [Import/Export](#importexport)
9. [ML Models](#ml-models)
10. [AI Brain](#ai-brain)
11. [Error Handling](#error-handling)

---

## Authentication

### Register User

Create a new user account.

**Endpoint**: `POST /api/auth/register`

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "created_at": "2026-01-30T10:00:00Z"
}
```

**Password Requirements**:
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

---

### Login

Authenticate and receive access token.

**Endpoint**: `POST /api/auth/login`

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Refresh Token

Get a new access token using refresh token.

**Endpoint**: `POST /api/auth/refresh`

**Authentication**: Not required

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Logout

Invalidate current session.

**Endpoint**: `POST /api/auth/logout`

**Authentication**: Required

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "message": "Successfully logged out"
}
```

---

## Transactions

### Create Transaction

Add a new transaction.

**Endpoint**: `POST /api/transactions`

**Authentication**: Required

**Request Body**:
```json
{
  "amount": 125.50,
  "date": "2026-01-30",
  "description": "Whole Foods Market",
  "type": "EXPENSE",
  "category": "Groceries"
}
```

**Fields**:
- `amount` (required): Transaction amount (positive number)
- `date` (required): Transaction date (YYYY-MM-DD)
- `description` (required): Transaction description
- `type` (required): "INCOME" or "EXPENSE"
- `category` (optional): Category name (auto-categorized if omitted)

**Response** (201 Created):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "amount": 125.50,
  "date": "2026-01-30",
  "description": "Whole Foods Market",
  "type": "EXPENSE",
  "category": "Groceries",
  "confidence_score": 0.95,
  "source": "MANUAL",
  "created_at": "2026-01-30T10:00:00Z",
  "updated_at": "2026-01-30T10:00:00Z"
}
```

---

### List Transactions

Get all transactions with optional filters.

**Endpoint**: `GET /api/transactions`

**Authentication**: Required

**Query Parameters**:
- `category` (optional): Filter by category
- `type` (optional): Filter by type (INCOME/EXPENSE)
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `search` (optional): Search in description
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Example**: `GET /api/transactions?category=Groceries&start_date=2026-01-01&limit=20`

**Response** (200 OK):
```json
{
  "transactions": [
    {
      "id": "uuid",
      "amount": 125.50,
      "date": "2026-01-30",
      "description": "Whole Foods Market",
      "type": "EXPENSE",
      "category": "Groceries",
      "confidence_score": 0.95,
      "source": "MANUAL",
      "created_at": "2026-01-30T10:00:00Z"
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

---

### Get Transaction

Get a single transaction by ID.

**Endpoint**: `GET /api/transactions/{transaction_id}`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "id": "uuid",
  "amount": 125.50,
  "date": "2026-01-30",
  "description": "Whole Foods Market",
  "type": "EXPENSE",
  "category": "Groceries",
  "confidence_score": 0.95,
  "source": "MANUAL",
  "created_at": "2026-01-30T10:00:00Z",
  "updated_at": "2026-01-30T10:00:00Z"
}
```

---

### Update Transaction

Update an existing transaction.

**Endpoint**: `PUT /api/transactions/{transaction_id}`

**Authentication**: Required

**Request Body** (all fields optional):
```json
{
  "amount": 130.00,
  "description": "Whole Foods Market - Updated",
  "category": "Groceries"
}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "amount": 130.00,
  "date": "2026-01-30",
  "description": "Whole Foods Market - Updated",
  "type": "EXPENSE",
  "category": "Groceries",
  "updated_at": "2026-01-30T11:00:00Z"
}
```

---

### Delete Transaction

Delete a transaction.

**Endpoint**: `DELETE /api/transactions/{transaction_id}`

**Authentication**: Required

**Response** (204 No Content)

---

## Budgets

### Create Budget

Create a new budget for a specific period.

**Endpoint**: `POST /api/budgets`

**Authentication**: Required

**Request Body**:
```json
{
  "name": "January 2026 Budget",
  "period_start": "2026-01-01",
  "period_end": "2026-01-31",
  "allocations": {
    "Groceries": 500.00,
    "Dining": 300.00,
    "Transportation": 200.00,
    "Utilities": 150.00,
    "Entertainment": 100.00
  }
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "January 2026 Budget",
  "period_start": "2026-01-01",
  "period_end": "2026-01-31",
  "allocations": {
    "Groceries": 500.00,
    "Dining": 300.00,
    "Transportation": 200.00,
    "Utilities": 150.00,
    "Entertainment": 100.00
  },
  "created_at": "2026-01-30T10:00:00Z"
}
```

---

### List Budgets

Get all budgets for the authenticated user.

**Endpoint**: `GET /api/budgets`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "budgets": [
    {
      "id": "uuid",
      "name": "January 2026 Budget",
      "period_start": "2026-01-01",
      "period_end": "2026-01-31",
      "total_allocated": 1250.00,
      "created_at": "2026-01-30T10:00:00Z"
    }
  ]
}
```

---

### Get Budget Progress

Get current spending vs budget for each category.

**Endpoint**: `GET /api/budgets/{budget_id}/progress`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "budget_id": "uuid",
  "period_start": "2026-01-01",
  "period_end": "2026-01-31",
  "progress": {
    "Groceries": {
      "allocated": 500.00,
      "spent": 425.50,
      "remaining": 74.50,
      "percentage": 85.1,
      "status": "ok"
    },
    "Dining": {
      "allocated": 300.00,
      "spent": 350.00,
      "remaining": -50.00,
      "percentage": 116.7,
      "status": "exceeded"
    }
  },
  "alerts": [
    {
      "category": "Dining",
      "message": "You have exceeded your budget by $50.00",
      "severity": "warning"
    }
  ]
}
```

---

### Get Budget Optimization Suggestions

Get AI-powered budget optimization suggestions.

**Endpoint**: `POST /api/budgets/{budget_id}/optimize`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "budget_id": "uuid",
  "suggestions": [
    {
      "category": "Dining",
      "current_allocation": 300.00,
      "suggested_allocation": 350.00,
      "reason": "You consistently overspend in this category by 17%",
      "confidence": 0.85
    },
    {
      "category": "Entertainment",
      "current_allocation": 100.00,
      "suggested_allocation": 50.00,
      "reason": "You underspend in this category by 50%",
      "confidence": 0.90
    }
  ],
  "total_reallocation": 0.00
}
```

---

### Apply Budget Optimization

Apply optimization suggestions to budget.

**Endpoint**: `PUT /api/budgets/{budget_id}/apply-optimization`

**Authentication**: Required

**Request Body**:
```json
{
  "suggestions": [
    {
      "category": "Dining",
      "new_allocation": 350.00
    },
    {
      "category": "Entertainment",
      "new_allocation": 50.00
    }
  ]
}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "name": "January 2026 Budget",
  "allocations": {
    "Groceries": 500.00,
    "Dining": 350.00,
    "Transportation": 200.00,
    "Utilities": 150.00,
    "Entertainment": 50.00
  },
  "updated_at": "2026-01-30T12:00:00Z"
}
```

---

## Goals

### Create Goal

Create a new financial goal.

**Endpoint**: `POST /api/goals`

**Authentication**: Required

**Request Body**:
```json
{
  "name": "Emergency Fund",
  "target_amount": 10000.00,
  "current_amount": 2500.00,
  "deadline": "2026-12-31",
  "category": "Savings"
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Emergency Fund",
  "target_amount": 10000.00,
  "current_amount": 2500.00,
  "deadline": "2026-12-31",
  "category": "Savings",
  "status": "ACTIVE",
  "progress_percentage": 25.0,
  "created_at": "2026-01-30T10:00:00Z"
}
```

---

### List Goals

Get all goals for the authenticated user.

**Endpoint**: `GET /api/goals`

**Authentication**: Required

**Query Parameters**:
- `status` (optional): Filter by status (ACTIVE/ACHIEVED/ARCHIVED)

**Response** (200 OK):
```json
{
  "goals": [
    {
      "id": "uuid",
      "name": "Emergency Fund",
      "target_amount": 10000.00,
      "current_amount": 2500.00,
      "deadline": "2026-12-31",
      "status": "ACTIVE",
      "progress_percentage": 25.0,
      "estimated_completion": "2026-11-15"
    }
  ]
}
```

---

### Update Goal

Update an existing goal.

**Endpoint**: `PUT /api/goals/{goal_id}`

**Authentication**: Required

**Request Body** (all fields optional):
```json
{
  "current_amount": 3000.00,
  "deadline": "2026-11-30"
}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "name": "Emergency Fund",
  "target_amount": 10000.00,
  "current_amount": 3000.00,
  "deadline": "2026-11-30",
  "progress_percentage": 30.0,
  "updated_at": "2026-01-30T12:00:00Z"
}
```

---

### Delete Goal

Delete a goal.

**Endpoint**: `DELETE /api/goals/{goal_id}`

**Authentication**: Required

**Response** (204 No Content)

---

## Predictions

### Get Expense Forecasts

Get AI-powered expense predictions for the next 30, 60, or 90 days.

**Endpoint**: `GET /api/predictions`

**Authentication**: Required

**Query Parameters**:
- `periods` (optional): Number of days to forecast (30, 60, or 90, default: 30)
- `category` (optional): Specific category to forecast

**Response** (200 OK):
```json
{
  "forecast_period": 30,
  "generated_at": "2026-01-30T10:00:00Z",
  "forecasts": {
    "Groceries": {
      "predicted_amount": 525.00,
      "confidence_interval": {
        "lower": 475.00,
        "upper": 575.00
      },
      "confidence": 0.85,
      "trend": "stable"
    },
    "Dining": {
      "predicted_amount": 320.00,
      "confidence_interval": {
        "lower": 280.00,
        "upper": 360.00
      },
      "confidence": 0.80,
      "trend": "increasing"
    }
  },
  "total_predicted": 1845.00
}
```

---

## Advice

### Get Personalized Advice

Get AI-generated financial advice based on spending patterns.

**Endpoint**: `GET /api/advice`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "generated_at": "2026-01-30T10:00:00Z",
  "advice": [
    {
      "id": "uuid",
      "title": "Reduce Dining Expenses",
      "message": "You're spending 17% more on dining than budgeted. Consider meal planning to reduce costs.",
      "priority": "high",
      "category": "Dining",
      "action_items": [
        "Plan meals for the week",
        "Cook at home 3 more times per week",
        "Set a daily dining limit of $15"
      ],
      "potential_savings": 50.00
    },
    {
      "id": "uuid",
      "title": "Emergency Fund Progress",
      "message": "Great job! You're 25% towards your emergency fund goal. Keep up the momentum.",
      "priority": "medium",
      "category": "Savings",
      "action_items": [
        "Continue current savings rate",
        "Consider automating monthly transfers"
      ]
    }
  ]
}
```

---

## Reports

### Generate Report

Generate a financial report for a custom date range.

**Endpoint**: `POST /api/reports/generate`

**Authentication**: Required

**Request Body**:
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "include_charts": true
}
```

**Response** (200 OK):
```json
{
  "report_id": "uuid",
  "period": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31"
  },
  "summary": {
    "total_income": 5000.00,
    "total_expenses": 3250.00,
    "net_savings": 1750.00,
    "savings_rate": 35.0
  },
  "income_breakdown": {
    "Salary": 4500.00,
    "Freelance": 500.00
  },
  "expense_breakdown": {
    "Groceries": 525.00,
    "Dining": 350.00,
    "Transportation": 200.00,
    "Utilities": 150.00,
    "Entertainment": 75.00,
    "Other": 1950.00
  },
  "budget_adherence": {
    "Groceries": {
      "budgeted": 500.00,
      "actual": 525.00,
      "variance": -25.00,
      "adherence": 95.2
    }
  },
  "generated_at": "2026-01-30T10:00:00Z"
}
```

---

### Export Report

Export a generated report in PDF or CSV format.

**Endpoint**: `GET /api/reports/{report_id}/export`

**Authentication**: Required

**Query Parameters**:
- `format` (required): "pdf" or "csv"

**Response** (200 OK):
- Content-Type: `application/pdf` or `text/csv`
- Content-Disposition: `attachment; filename="report_2026-01.pdf"`

---

## Import/Export

### Import Transactions

Upload a CSV or XLSX file to import transactions.

**Endpoint**: `POST /api/import/transactions`

**Authentication**: Required

**Content-Type**: `multipart/form-data`

**Request Body**:
- `file` (required): CSV or XLSX file
- `skip_duplicates` (optional): Boolean (default: true)

**CSV Format**:
```csv
Date,Description,Amount,Type,Category
2026-01-15,Whole Foods Market,125.50,EXPENSE,Groceries
2026-01-16,Salary Deposit,5000.00,INCOME,Salary
```

**Response** (200 OK):
```json
{
  "imported": 45,
  "skipped": 3,
  "errors": 2,
  "details": {
    "duplicates_skipped": 3,
    "invalid_rows": [
      {
        "row": 10,
        "error": "Invalid date format"
      },
      {
        "row": 15,
        "error": "Amount must be a number"
      }
    ]
  }
}
```

---

### Export Transactions

Export transactions to CSV format.

**Endpoint**: `GET /api/export/transactions`

**Authentication**: Required

**Query Parameters**:
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `category` (optional): Filter by category
- `type` (optional): Filter by type (INCOME/EXPENSE)

**Response** (200 OK):
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="transactions_2026-01.csv"`

---

### Download Import Template

Download a sample CSV or XLSX template for importing transactions.

**Endpoint**: `GET /api/import/template`

**Authentication**: Required

**Query Parameters**:
- `format` (required): "csv" or "xlsx"

**Response** (200 OK):
- Content-Type: `text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="import_template.csv"`

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": "Error type",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  }
}
```

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `204 No Content`: Request successful, no content to return
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required or failed
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate)
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Common Error Examples

**Validation Error** (400):
```json
{
  "error": "Validation Error",
  "message": "Invalid request data",
  "details": {
    "amount": "Amount must be a positive number",
    "date": "Date must be in YYYY-MM-DD format"
  }
}
```

**Authentication Error** (401):
```json
{
  "error": "Unauthorized",
  "message": "Invalid or expired token"
}
```

**Not Found Error** (404):
```json
{
  "error": "Not Found",
  "message": "Transaction with ID 'uuid' not found"
}
```

---

## Rate Limiting

API requests are rate-limited to prevent abuse:

- **Authenticated requests**: 1000 requests per hour
- **Unauthenticated requests**: 100 requests per hour

Rate limit headers are included in all responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1643558400
```

---

## Pagination

List endpoints support pagination using `limit` and `offset` parameters:

- `limit`: Number of results per page (default: 50, max: 100)
- `offset`: Number of results to skip (default: 0)

**Example**: `GET /api/transactions?limit=20&offset=40`

Pagination metadata is included in responses:
```json
{
  "data": [...],
  "total": 150,
  "limit": 20,
  "offset": 40,
  "has_more": true
}
```

---

## ML Models

### ML Status

Get overall ML system status.

**Endpoint**: `GET /api/ml/status`

**Authentication**: Not required

**Response** (200):
```json
{
  "global_model_loaded": true,
  "total_categories": 15,
  "model_type": "TF-IDF + Naive Bayes"
}
```

---

### Global Model Info

**Endpoint**: `GET /api/ml/models/global`

**Authentication**: Not required

---

### User Model Status

**Endpoint**: `GET /api/ml/models/user/me`

**Authentication**: Required (JWT)

**Response** (200):
```json
{
  "has_model": true,
  "correction_count": 25,
  "accuracy": 0.95,
  "last_trained": "2026-02-01T10:00:00Z"
}
```

---

### Categorize Transaction

**Endpoint**: `POST /api/ml/categorize`

**Authentication**: Required (JWT)

**Request Body**:
```json
{
  "description": "STARBUCKS COFFEE #12345",
  "amount": 5.50
}
```

**Response** (200):
```json
{
  "category": "Food & Dining",
  "confidence": 0.999,
  "model_type": "GLOBAL",
  "llm_enhanced": false
}
```

---

### Batch Categorization

**Endpoint**: `POST /api/ml/categorize/batch`

**Authentication**: Required (JWT)

**Request Body**:
```json
{
  "transactions": [
    {"description": "UBER TRIP", "amount": 15},
    {"description": "NETFLIX MONTHLY", "amount": 14.99}
  ]
}
```

---

### Submit Correction

Submit a categorization correction to improve the user's personalized model.

**Endpoint**: `POST /api/ml/corrections`

**Authentication**: Required (JWT)

**Request Body**:
```json
{
  "description": "DOORDASH*THAI FOOD",
  "correct_category": "Food & Dining"
}
```

---

### Train User Model

Manually trigger training of the user's personalized ML model.

**Endpoint**: `POST /api/ml/models/user/me/train`

**Authentication**: Required (JWT)

---

### Delete User Model

Delete the current user's personalized ML model.

**Endpoint**: `DELETE /api/ml/models/user/me`

**Authentication**: Required (JWT)

---

### Get Categories

**Endpoint**: `GET /api/ml/categories`

**Authentication**: Not required

---

## AI Brain

The AI Brain endpoints require the GPU-powered LLM service to be running (`docker compose --profile gpu up`). All AI endpoints are protected by InputGuard (prompt injection detection) and OutputGuard (PII masking, harmful content filtering).

### AI Status

**Endpoint**: `GET /api/ai/status`

**Authentication**: Not required

**Rate Limit**: 30 requests/minute

---

### Chat

Conversational financial assistant.

**Endpoint**: `POST /api/ai/chat`

**Authentication**: Required (JWT)

**Rate Limit**: 5/minute, 100/hour

**Request Body**:
```json
{
  "message": "How can I reduce my food spending?",
  "context": {
    "monthly_income": 5000,
    "spending": {"Food & Dining": 800, "Shopping": 400}
  }
}
```

---

### Analyze

Request comprehensive financial analysis.

**Endpoint**: `POST /api/ai/analyze`

**Authentication**: Required (JWT)

**Rate Limit**: 5/minute, 100/hour

---

### Parse Transaction

Parse a raw transaction description into structured data using AI + RAG.

**Endpoint**: `POST /api/ai/parse-transaction`

**Authentication**: Required (JWT)

**Rate Limit**: 30/minute

**Request Body**:
```json
{
  "description": "WHOLEFDS 12345 AUSTIN TX $89.52"
}
```

**Response** (200):
```json
{
  "merchant": "Whole Foods Market",
  "amount": 89.52,
  "category": "Groceries",
  "confidence": 0.94,
  "is_recurring": false
}
```

---

### Smart Advice

Get personalized AI-powered financial advice.

**Endpoint**: `POST /api/ai/smart-advice`

**Authentication**: Required (JWT)

**Rate Limit**: 5/minute, 100/hour

---

### Submit Category Correction (Feedback)

Submit a correction to improve the RAG system's merchant database. When 3+ users submit the same correction, the merchant database auto-updates.

**Endpoint**: `POST /api/ai/feedback/correction`

**Authentication**: Required (JWT)

**Rate Limit**: 30/minute

**Request Body**:
```json
{
  "merchant_raw": "WHOLEFDS 12345 AUSTIN TX",
  "original_category": "Fast Food",
  "corrected_category": "Groceries"
}
```

---

### Feedback Stats

Get feedback statistics.

**Endpoint**: `GET /api/ai/feedback/stats`

**Authentication**: Required (JWT)

**Rate Limit**: 10/minute

---

## Support

For API support:
- **Swagger UI**: `http://localhost:8000/docs` (interactive, auto-generated)
- **GitHub Issues**: [github.com/cyberkunju/Finehance/issues](https://github.com/cyberkunju/Finehance/issues)

---

## Changelog

### Version 1.0.0 (2026-01-30)
- Initial API release
- Authentication endpoints
- Transaction management
- Budget tracking
- Goal tracking
- Predictions and advice
- Reports and analytics
- Import/export functionality
