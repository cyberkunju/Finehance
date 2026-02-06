# Phase 0 — Critical Security & Bug Fixes

> **Priority:** MUST DO FIRST — nothing else matters until auth is enforced  
> **Estimated Effort:** 2-3 days  
> **Status:** ~88% complete (all code changes done, final validation remaining)  
> **Files Modified:** 17  
> **Files Created:** 1 (`app/dependencies.py`)

---

## Task 0.1 — Create Reusable Auth Dependency

### Problem
There is NO reusable `get_current_user` dependency. The only auth check exists inside `app/routes/auth.py`'s `/me` endpoint handler, which manually calls `AuthService.get_current_user(token)`. Every other route accepts `user_id` as an **unauthenticated query parameter** — meaning anyone can impersonate any user.

### What To Do

**Create `app/dependencies.py`** — a new file with reusable FastAPI dependencies:

```python
"""Shared FastAPI dependencies for authentication and authorization."""

from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT token.
    
    Returns the full User ORM object so routes can access user.id,
    user.email, etc. without any additional DB queries.
    
    Raises HTTPException 401 if token is invalid/expired.
    """
    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    current_user: User = Depends(get_current_user),
) -> UUID:
    """
    Shorthand dependency that returns just the user's UUID.
    Use this when you only need the ID, not the full user object.
    """
    return current_user.id
```

### Verification
- Import `get_current_user` and `get_current_user_id` in any route file
- Call an endpoint without a Bearer token → expect 401
- Call with a valid token → expect the user object/ID injected

---

## Task 0.2 — Wire Auth Into ALL Route Files

### Problem
Every route file (except `/me`) accepts `user_id: UUID = Query(...)` as an unauthenticated query parameter. This means **any caller can pass any UUID and access/modify/delete another user's data**.

### What To Do — Per-File Instructions

The pattern is the same for every file:

1. **Remove** `user_id: UUID = Query(...)` from function parameters
2. **Add** `user_id: UUID = Depends(get_current_user_id)` (imported from `app.dependencies`)
3. **Remove** the `Query` import if no longer needed

---

#### File: `app/routes/transactions.py`

**Current** (5 endpoints, all have `user_id: UUID = Query(...)`):

```python
# Example: create_transaction at line 46
async def create_transaction(
    transaction: TransactionCreate,
    user_id: UUID = Query(..., description="User ID"),
    service: TransactionService = Depends(get_transaction_service),
):
```

**Change to:**

```python
from app.dependencies import get_current_user_id

async def create_transaction(
    transaction: TransactionCreate,
    user_id: UUID = Depends(get_current_user_id),
    service: TransactionService = Depends(get_transaction_service),
):
```

**Apply this change to ALL 5 endpoints:**
- `create_transaction` (line 46)
- `list_transactions` (line 74)
- `get_transaction` (line 121)
- `update_transaction` (line 145)
- `delete_transaction` (line 178)

Also remove `from fastapi import ... Query` if Query is no longer used by any param. (Check — some endpoints use `Query` for `page`, `page_size`, `category`, etc.)

---

#### File: `app/routes/budgets.py`

**8 endpoints, all have `user_id: UUID = Query(...)`**

Same pattern — replace `user_id: UUID = Query(...)` with `user_id: UUID = Depends(get_current_user_id)` in:
- `create_budget` (line 53)
- `list_budgets` (line 77)
- `get_budget` (line 95)
- `get_budget_progress` (line 118)
- `get_optimization_suggestions` (line 165)
- `apply_optimization` (line 213)
- `update_budget` (line 261)
- `delete_budget` (line 299)

---

#### File: `app/routes/goals.py`

**8 endpoints, all have `user_id: UUID = Query(...)`**

Same pattern in:
- `create_goal` (line 30)
- `list_goals` (line 57)
- `get_goal` (line 77)
- `get_goal_progress` (line 100)
- `update_goal_progress` (line 133)
- `get_goal_risk_alerts` (line 162) — **ALSO**: move this route BEFORE the `{goal_id}` routes to fix the route ordering bug
- `update_goal` (line 186)
- `delete_goal` (line 224)

**Additional fix — Route ordering:**
Move `get_goal_risk_alerts` (path `/risks/alerts`) to be declared BEFORE any `/{goal_id}` routes. Currently it's after `/{goal_id}/progress`, so FastAPI tries to parse "risks" as a UUID first. It works by accident (UUID validation rejects "risks"), but it's fragile.

---

#### File: `app/routes/predictions.py`

**3 endpoints, all have `user_id: UUID = Query(...)`**

Same pattern in:
- `get_expense_forecasts` (line 22)
- `get_category_forecast` (line 61)
- `get_spending_anomalies` (line 100)

**Additional fix:** Add category validation — `category` is currently a raw string path parameter with no validation. Add an enum or a list check:

```python
from app.ml.categorization_engine import VALID_CATEGORIES  # or define in schemas

@router.get("/forecast/{category}")
async def get_category_forecast(
    category: str,
    user_id: UUID = Depends(get_current_user_id),
    ...
):
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    ...
```

---

#### File: `app/routes/advice.py`

**3 endpoints, all have `user_id: UUID = Query(...)`**

Same pattern in:
- `get_personalized_advice` (line 30)
- `get_spending_alerts` (line 72)
- `get_savings_opportunities` (line 102)

**Additional fix:** The cache key is `advice:{user_id}:{max_recommendations}`. Since auth is now enforced, cache poisoning is no longer possible — the `user_id` comes from the JWT, not from user input. This is automatically fixed by Task 0.2.

---

#### File: `app/routes/reports.py`

**3 endpoints:**
- `generate_report` (line 28) — `user_id` is inside `ReportGenerateRequest` body
- `export_report_csv` (line 89) — `user_id: UUID = Query(...)`
- `export_report_pdf` (line 143) — `user_id: UUID = Query(...)`

**For `generate_report`:** Remove `user_id` from the `ReportGenerateRequest` schema and inject it from auth:

```python
async def generate_report(
    request: ReportGenerateRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Use user_id from auth, not from request body
    report_service = ReportService(db)
    report = await report_service.generate_report(
        user_id=user_id,  # NOT request.user_id
        start_date=request.start_date,
        end_date=request.end_date,
        ...
    )
```

**Also update `app/schemas/report.py`:** Remove `user_id` field from `ReportGenerateRequest` — it's a security concern to let users specify their own user_id in request bodies.

**For CSV/PDF exports:** Replace `user_id: UUID = Query(...)` with `user_id: UUID = Depends(get_current_user_id)`.

---

#### File: `app/routes/file_import.py`

**2 endpoints with `user_id: UUID = Query(...)`:**
- `import_transactions` (line 20)
- `export_transactions` (line 120)

Same pattern. The 3rd endpoint (`download_template`, line 184) has no `user_id` — that's correct (templates are universal).

---

#### File: `app/routes/ml.py`

This file is more complex — it mixes query params, path params, and request body user_ids:

| Endpoint | Current user_id source | Change To |
|----------|----------------------|-----------|
| `get_ml_status` | None | No auth needed (system status) |
| `get_global_model_status` | None | No auth needed (public info) |
| `get_user_model_status` | Path param `{user_id}` | `Depends(get_current_user_id)` — users can only see their own models |
| `categorize_transaction` | `request.user_id` (body) | `Depends(get_current_user_id)` — pass to engine |
| `batch_categorize` | `request.user_id` (body) | `Depends(get_current_user_id)` |
| `submit_correction` | `request.user_id` (body) | `Depends(get_current_user_id)` |
| `train_user_model` | Path param `{user_id}` | `Depends(get_current_user_id)` |
| `get_categories` | None | No auth needed (public info) |
| `delete_user_model` | Path param `{user_id}` | `Depends(get_current_user_id)` — **CRITICAL: prevents anyone from deleting any user's model** |

**For body-based user_ids** (`CategorizeRequest`, `BatchCategorizeRequest`, `CorrectionRequest`): Remove `user_id` from these schema classes and inject via auth dependency instead.

**For path-based user_ids**: Remove `{user_id}` from the path, use auth dependency:

```python
# BEFORE:
@router.delete("/models/user/{user_id}")
async def delete_user_model(user_id: UUID, ...):

# AFTER:
@router.delete("/models/user/me")
async def delete_user_model(
    user_id: UUID = Depends(get_current_user_id), ...
):
```

---

#### File: `app/routes/ai.py`

This file already has rate limiting but no auth. The `user_id` comes from request bodies (optional in some endpoints):

| Endpoint | Change |
|----------|--------|
| `get_ai_status` | No auth needed (system status) |
| `chat` | Add `Depends(get_current_user_id)` — remove `user_id` from `ChatRequest` |
| `analyze` | Add `Depends(get_current_user_id)` |
| `parse_transaction` | Add `Depends(get_current_user_id)` |
| `smart_advice` | Add `Depends(get_current_user_id)` |
| `submit_correction` | Add `Depends(get_current_user_id)` |
| `get_feedback_stats` | Add auth — stats should be user-scoped or admin-only |

---

#### File: `app/routes/auth.py`

**Refactor the `/me` endpoint** to use the new shared dependency:

```python
# BEFORE (lines 180-210):
@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> UserResponse:
    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(token)
        ...

# AFTER:
from app.dependencies import get_current_user

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        created_at=current_user.created_at.isoformat(),
    )
```

Remove the local `OAuth2PasswordBearer` declaration since it now lives in `app/dependencies.py`.

---

## Task 0.3 — Stop Leaking Exception Details

### Problem
Every route catches `Exception as e` and returns `str(e)` in the HTTP 500 response:

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")
```

This bypasses the global exception handler in `main.py` (which redacts errors when `debug=False`) because these are **explicit** HTTPExceptions, not unhandled exceptions.

### What To Do

In ALL route files, change every `except Exception as e` block to use a generic message and log the real error:

```python
# IN EVERY ROUTE FILE, change:
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

# TO:
except Exception as e:
    logger.error(f"Failed to create transaction: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
```

**Files to modify (every route file):**
- `app/routes/transactions.py` — 5 handlers
- `app/routes/budgets.py` — 8 handlers
- `app/routes/goals.py` — 8 handlers
- `app/routes/predictions.py` — 3 handlers
- `app/routes/advice.py` — 3 handlers
- `app/routes/reports.py` — 3 handlers
- `app/routes/file_import.py` — 2 handlers
- `app/routes/ml.py` — 6 handlers
- `app/routes/ai.py` — 5 handlers

**Ensure a logger is defined at the top of each file:**

```python
import logging
logger = logging.getLogger(__name__)
```

### Keep Specific 4xx Errors
Do NOT change specific error handlers like:
```python
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

These are intentional user-facing validation errors and should remain. Only change the catch-all `Exception` handler.

---

## Task 0.4 — Fix Division-by-Zero Bug in Advice Generator

### Problem
In `app/services/advice_generator.py` at lines 231-234:

```python
total_days = (goal.deadline - goal.created_at.date()).days
time_elapsed_percent = (
    (today - goal.created_at.date()).days / total_days
) * 100
```

If `goal.deadline == goal.created_at.date()`, then `total_days = 0` and `time_elapsed_percent` crashes with `ZeroDivisionError`.

Note: The **similar code in `app/services/goal_service.py`** (lines 168-172) already has a `if days_since_creation > 0:` guard and is safe.

### What To Do

Add a guard before the division:

```python
total_days = (goal.deadline - goal.created_at.date()).days
if total_days > 0:
    time_elapsed_percent = (
        (today - goal.created_at.date()).days / total_days
    ) * 100
else:
    time_elapsed_percent = 100.0  # Goal deadline is today or already passed
```

### Verification
- Create a goal with `deadline = today`
- Call the advice endpoint → should NOT crash
- Should return advice indicating the goal deadline has arrived

---

## Task 0.5 — Fix Category NULL Mismatch

### Problem
- **Model** (`app/models/transaction.py` line 47): `category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)`
- **Schema** (`app/schemas/transaction.py` lines 40-42): `category: Optional[str] = Field(None, ...)`

The schema allows `category=None`, but the database column is `NOT NULL`. When a transaction is created without providing a category AND the auto-categorization fails to assign one, the DB insert will crash with `IntegrityError`.

### What To Do

**Option A (Recommended):** Add a default in the model so auto-categorization always has a fallback:

In `app/services/transaction_service.py`, in the `create_transaction` method, after categorization:

```python
# After auto-categorization attempt, ensure category is never None
if not transaction.category:
    transaction.category = "Uncategorized"
```

AND update the schema to document this:

```python
# app/schemas/transaction.py
category: Optional[str] = Field(
    None,
    max_length=50,
    description="Transaction category. Auto-assigned to 'Uncategorized' if not provided and auto-categorization fails."
)
```

### Verification
- Create a transaction with `category=None` and a gibberish description that the ML model can't categorize
- Transaction should be created with `category="Uncategorized"` instead of crashing

---

## Task 0.6 — Add `is_active` Flag to User Model

### Problem
The `User` model has no `is_active` field. There's no way to deactivate/suspend a user without deleting their data. This is needed for:
- Account suspension
- Deactivation without losing data
- Admin operations

### What To Do

In `app/models/user.py`, add:

```python
is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
```

Then update `app/dependencies.py`'s `get_current_user` to check:

```python
async def get_current_user(...) -> User:
    ...
    user = await auth_service.get_current_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found", ...)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user
```

Create an Alembic migration:

```bash
alembic revision --autogenerate -m "add_is_active_to_users"
alembic upgrade head
```

---

## Granular Checklist — Task 0.1

- [x] Create `app/dependencies.py` file
- [x] Add `OAuth2PasswordBearer` import with `tokenUrl="/api/auth/login"`
- [x] Implement `get_current_user()` dependency — returns full `User` ORM object
- [x] Add `HTTPException 401` for invalid/expired tokens
- [x] Add `WWW-Authenticate: Bearer` header to 401 responses
- [x] Implement `get_current_user_id()` dependency — returns just `UUID`
- [x] Test: import dependency in a route file and verify it loads
- [x] Test: call endpoint without Bearer token → expect 401
- [x] Test: call endpoint with valid token → expect user injected

---

## Granular Checklist — Task 0.2 (Auth Wiring)

### `app/routes/transactions.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `create_transaction` — replace `user_id: UUID = Query(...)` with `user_id: UUID = Depends(get_current_user_id)`
- [x] Change `list_transactions` — replace `user_id: UUID = Query(...)` with `Depends(get_current_user_id)`
- [x] Change `get_transaction` — replace `user_id: UUID = Query(...)` with `Depends(get_current_user_id)`
- [x] Change `update_transaction` — replace `user_id: UUID = Query(...)` with `Depends(get_current_user_id)`
- [x] Change `delete_transaction` — replace `user_id: UUID = Query(...)` with `Depends(get_current_user_id)`
- [x] Remove `Query` import if no longer used by any param (check `page`, `page_size`, `category` params still need it)
- [x] Verify: call any endpoint without token → 401

### `app/routes/budgets.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `create_budget` — `Depends(get_current_user_id)`
- [x] Change `list_budgets` — `Depends(get_current_user_id)`
- [x] Change `get_budget` — `Depends(get_current_user_id)`
- [x] Change `get_budget_progress` — `Depends(get_current_user_id)`
- [x] Change `get_optimization_suggestions` — `Depends(get_current_user_id)`
- [x] Change `apply_optimization` — `Depends(get_current_user_id)`
- [x] Change `update_budget` — `Depends(get_current_user_id)`
- [x] Change `delete_budget` — `Depends(get_current_user_id)`
- [x] Verify: call any endpoint without token → 401

### `app/routes/goals.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `create_goal` — `Depends(get_current_user_id)`
- [x] Change `list_goals` — `Depends(get_current_user_id)`
- [x] Change `get_goal` — `Depends(get_current_user_id)`
- [x] Change `get_goal_progress` — `Depends(get_current_user_id)`
- [x] Change `update_goal_progress` — `Depends(get_current_user_id)`
- [x] Change `get_goal_risk_alerts` — `Depends(get_current_user_id)`
- [x] Change `update_goal` — `Depends(get_current_user_id)`
- [x] Change `delete_goal` — `Depends(get_current_user_id)`
- [x] Move `get_goal_risk_alerts` BEFORE `{goal_id}` routes to fix route ordering bug
- [x] Verify: call any endpoint without token → 401

### `app/routes/predictions.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `get_expense_forecasts` — `Depends(get_current_user_id)`
- [x] Change `get_category_forecast` — `Depends(get_current_user_id)`
- [x] Change `get_spending_anomalies` — `Depends(get_current_user_id)`
- [x] Add category validation — check `category` param against `VALID_CATEGORIES`
- [x] Verify: call any endpoint without token → 401

### `app/routes/advice.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `get_personalized_advice` — `Depends(get_current_user_id)`
- [x] Change `get_spending_alerts` — `Depends(get_current_user_id)`
- [x] Change `get_savings_opportunities` — `Depends(get_current_user_id)`
- [x] Verify: call any endpoint without token → 401

### `app/routes/reports.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `generate_report` — add `user_id: UUID = Depends(get_current_user_id)` as function param
- [x] Remove `user_id` field from `ReportGenerateRequest` schema
- [x] Pass `user_id` from auth dependency instead of `request.user_id`
- [x] Change `export_report_csv` — `Depends(get_current_user_id)`
- [x] Change `export_report_pdf` — `Depends(get_current_user_id)`
- [x] Verify: call any endpoint without token → 401

### `app/routes/file_import.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Change `import_transactions` — `Depends(get_current_user_id)`
- [x] Change `export_transactions` — `Depends(get_current_user_id)`
- [x] Keep `download_template` with no auth (templates are public)
- [x] Verify: call import/export without token → 401

### `app/routes/ml.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Keep `get_ml_status` — no auth needed (system status)
- [x] Keep `get_global_model_status` — no auth needed (public info)
- [x] Change `get_user_model_status` — remove `{user_id}` path param, use `Depends(get_current_user_id)`
- [x] Change `categorize_transaction` — use `Depends(get_current_user_id)`, remove `user_id` from `CategorizeRequest`
- [x] Change `batch_categorize` — use `Depends(get_current_user_id)`, remove `user_id` from `BatchCategorizeRequest`
- [x] Change `submit_correction` — use `Depends(get_current_user_id)`, remove `user_id` from `CorrectionRequest`
- [x] Change `train_user_model` — remove `{user_id}` path param, use `Depends(get_current_user_id)`
- [x] Keep `get_categories` — no auth needed (public info)
- [x] Change `delete_user_model` — remove `{user_id}` path param, use `Depends(get_current_user_id)`
- [x] Update all affected schema classes to remove `user_id` field
- [x] Verify: call protected endpoints without token → 401

### `app/routes/ai.py`
- [x] Add `from app.dependencies import get_current_user_id` import
- [x] Keep `get_ai_status` — no auth needed (system status)
- [x] Change `chat` — add `Depends(get_current_user_id)`, remove `user_id` from `ChatRequest`
- [x] Change `analyze` — add `Depends(get_current_user_id)`
- [x] Change `parse_transaction` — add `Depends(get_current_user_id)`
- [x] Change `smart_advice` — add `Depends(get_current_user_id)`
- [x] Change `submit_correction` — add `Depends(get_current_user_id)`
- [x] Change `get_feedback_stats` — add auth (user-scoped or admin-only)
- [x] Update affected schema classes to remove `user_id` field
- [x] Verify: call protected endpoints without token → 401

### `app/routes/auth.py`
- [x] Add `from app.dependencies import get_current_user` import
- [x] Refactor `/me` endpoint to use `current_user: User = Depends(get_current_user)`
- [x] Remove manual token parsing from `/me` handler
- [x] Remove local `OAuth2PasswordBearer` declaration (now lives in `dependencies.py`)
- [x] Verify: call `/me` with valid token → 200
- [x] Verify: call `/me` without token → 401

---

## Granular Checklist — Task 0.3 (Stop Leaking Exceptions)

### Setup
- [x] Add `import logging` to every route file that doesn't have it
- [x] Add `logger = logging.getLogger(__name__)` to every route file

### `app/routes/transactions.py`
- [x] Change `create_transaction` `except Exception` — log error, return generic message
- [x] Change `list_transactions` `except Exception` — log error, return generic message
- [x] Change `get_transaction` `except Exception` — log error, return generic message
- [x] Change `update_transaction` `except Exception` — log error, return generic message
- [x] Change `delete_transaction` `except Exception` — log error, return generic message

### `app/routes/budgets.py`
- [x] Change `create_budget` `except Exception` — log + generic message
- [x] Change `list_budgets` `except Exception` — log + generic message
- [x] Change `get_budget` `except Exception` — log + generic message
- [x] Change `get_budget_progress` `except Exception` — log + generic message
- [x] Change `get_optimization_suggestions` `except Exception` — log + generic message
- [x] Change `apply_optimization` `except Exception` — log + generic message
- [x] Change `update_budget` `except Exception` — log + generic message
- [x] Change `delete_budget` `except Exception` — log + generic message

### `app/routes/goals.py`
- [x] Change `create_goal` `except Exception` — log + generic message
- [x] Change `list_goals` `except Exception` — log + generic message
- [x] Change `get_goal` `except Exception` — log + generic message
- [x] Change `get_goal_progress` `except Exception` — log + generic message
- [x] Change `update_goal_progress` `except Exception` — log + generic message
- [x] Change `get_goal_risk_alerts` `except Exception` — log + generic message
- [x] Change `update_goal` `except Exception` — log + generic message
- [x] Change `delete_goal` `except Exception` — log + generic message

### `app/routes/predictions.py`
- [x] Change `get_expense_forecasts` `except Exception` — log + generic message
- [x] Change `get_category_forecast` `except Exception` — log + generic message
- [x] Change `get_spending_anomalies` `except Exception` — log + generic message

### `app/routes/advice.py`
- [x] Change `get_personalized_advice` `except Exception` — log + generic message
- [x] Change `get_spending_alerts` `except Exception` — log + generic message
- [x] Change `get_savings_opportunities` `except Exception` — log + generic message

### `app/routes/reports.py`
- [x] Change `generate_report` `except Exception` — log + generic message
- [x] Change `export_report_csv` `except Exception` — log + generic message
- [x] Change `export_report_pdf` `except Exception` — log + generic message

### `app/routes/file_import.py`
- [x] Change `import_transactions` `except Exception` — log + generic message
- [x] Change `export_transactions` `except Exception` — log + generic message

### `app/routes/ml.py`
- [x] Change all 6 relevant handlers `except Exception` — log + generic message

### `app/routes/ai.py`
- [x] Change all 5 relevant handlers `except Exception` — log + generic message

### Validation
- [x] Keep specific `ValueError`/`400` handlers as-is (user-facing validation errors)
- [x] Verify: trigger an internal error → response shows generic message, NOT stack trace
- [x] Verify: server log shows the real error with `exc_info=True`

---

## Granular Checklist — Task 0.4 (Division-by-Zero Fix)

- [x] Open `app/services/advice_generator.py` line 231
- [x] Add `if total_days > 0:` guard before division
- [x] Add `else: time_elapsed_percent = 100.0` fallback
- [x] Verify: create a goal with `deadline = today`
- [x] Verify: call advice endpoint → no crash
- [x] Verify: returns advice indicating goal deadline has arrived

---

## Granular Checklist — Task 0.5 (Category NULL Mismatch)

- [x] Open `app/services/transaction_service.py` → `create_transaction` method
- [x] Add `if not transaction.category: transaction.category = "Uncategorized"` after auto-categorization
- [x] Open `app/schemas/transaction.py`
- [x] Update `category` field description to document fallback behavior
- [x] Verify: create transaction with `category=None` and gibberish description
- [x] Verify: transaction created with `category="Uncategorized"` instead of crashing

---

## Granular Checklist — Task 0.6 (is_active Flag)

- [x] Open `app/models/user.py`
- [x] Add `is_active: Mapped[bool] = mapped_column(default=True, server_default="true")`
- [x] Open `app/dependencies.py`
- [x] Add `if not user.is_active: raise HTTPException(403, "Account is deactivated")`
- [x] Create Alembic migration: `alembic revision --autogenerate -m "add_is_active_to_users"`
- [x] Run migration: `alembic upgrade head`
- [x] Verify: active user can access endpoints normally
- [x] Verify: deactivated user gets 403

---

## Final Validation

- [ ] Run ALL existing tests (`pytest tests/ -v`)
- [ ] All tests pass (or known failures documented)
- [ ] Manual test: register a new user
- [ ] Manual test: login → get access token
- [ ] Manual test: call `/api/transactions` with token → 200
- [ ] Manual test: call `/api/transactions` without token → 401
- [ ] Manual test: call `/api/transactions` with expired token → 401
- [ ] Manual test: call `/api/auth/me` with token → 200
- [ ] Manual test: trigger an error → response is generic, no stack trace
- [ ] `grep -r "user_id.*Query" app/routes/` returns 0 results
- [ ] `grep -r "str(e)" app/routes/` returns 0 results (in except blocks)
