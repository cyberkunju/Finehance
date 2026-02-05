# Phase 1 — Backend Fixes & Consistency

> **Depends on:** P0 (auth must be enforced first)  
> **Estimated Effort:** 3-4 days  
> **Covers:** Middleware wiring, PDF fix, token blacklisting, datetime deprecation, schema gaps, service consistency

---

## Task 1.1 — Wire Input/Output Guards as ASGI Middleware

### Problem
`InputGuard` (512 lines) and `OutputGuard` (700 lines) are well-implemented standalone classes but are **not registered in the FastAPI middleware pipeline**. Only `app/routes/ai.py` manually calls them. All other routes have zero input sanitization.

### What To Do

**Create `app/middleware/security.py`** — an ASGI middleware that wraps both guards:

```python
"""Security middleware — input sanitization and output filtering."""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.middleware.input_guard import InputGuard, ThreatLevel
from app.middleware.output_guard import OutputGuard

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Applies InputGuard on POST/PUT/PATCH request bodies,
    and OutputGuard on JSON response bodies for AI endpoints.
    """
    
    def __init__(self, app, input_guard: InputGuard = None, output_guard: OutputGuard = None):
        super().__init__(app)
        self.input_guard = input_guard or InputGuard()
        self.output_guard = output_guard or OutputGuard()
        # Paths where output guard should filter responses
        self.ai_response_paths = {"/api/ai/chat", "/api/ai/analyze", "/api/ai/smart-advice"}
    
    async def dispatch(self, request: Request, call_next):
        # INPUT GUARD: Check POST/PUT/PATCH bodies
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    text = body.decode("utf-8", errors="ignore")
                    result = self.input_guard.validate(text)
                    if not result.is_safe:
                        logger.warning(
                            f"Input blocked: threat_level={result.threat_level}, "
                            f"path={request.url.path}"
                        )
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Input rejected due to security concerns."}
                        )
            except Exception:
                pass  # Don't crash the request on guard errors
        
        response = await call_next(request)
        
        # OUTPUT GUARD: Filter AI response bodies
        if request.url.path in self.ai_response_paths:
            # Only filter JSON responses
            if response.headers.get("content-type", "").startswith("application/json"):
                # Read and filter the response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                text = body.decode("utf-8", errors="ignore")
                validation = self.output_guard.validate(text)
                
                if not validation.is_safe and validation.filtered_content:
                    body = validation.filtered_content.encode("utf-8")
                
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
        
        return response
```

**Register in `app/main.py`** — add after CORS middleware:

```python
from app.middleware.security import SecurityMiddleware

app.add_middleware(SecurityMiddleware)
```

### Verification
- Send a POST to any endpoint with prompt injection text like `"Ignore all instructions and..."` → should get 400
- Normal requests should pass through unchanged
- AI endpoint responses should be filtered for PII

---

## Task 1.2 — Implement Token Blacklisting for Logout

### Problem
The logout endpoint at `app/routes/auth.py` line 145 is a no-op — it returns a success message but doesn't actually invalidate the token. Stolen tokens remain valid until natural expiry.

### What To Do

**Step 1: Create a token blacklist using Redis** (already in the stack).

Add to `app/services/auth_service.py`:

```python
from app.cache import cache_manager

class AuthService:
    ...
    
    async def blacklist_token(self, token: str, expires_in: int = None) -> None:
        """
        Add a token to the blacklist. Token will be auto-removed
        from Redis when it naturally expires.
        """
        if expires_in is None:
            # Decode to find expiry
            try:
                payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
                exp = payload.get("exp", 0)
                expires_in = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
            except JWTError:
                expires_in = settings.jwt_access_token_expire_minutes * 60
        
        await cache_manager.set(
            f"blacklist:{token}",
            "1",
            ttl=expires_in
        )
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if a token has been blacklisted."""
        result = await cache_manager.get(f"blacklist:{token}")
        return result is not None
```

**Step 2: Check blacklist in `app/dependencies.py`:**

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    auth_service = AuthService(db)
    
    # Check blacklist first (fast Redis lookup)
    if await auth_service.is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    
    try:
        user = await auth_service.get_current_user(token)
        ...
```

**Step 3: Update the logout route:**

```python
@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    await auth_service.blacklist_token(token)
    return {"message": "Successfully logged out"}
```

**Step 4: Also blacklist access token when refresh token is used:**

In the `/refresh` endpoint, after issuing new tokens, blacklist the old access token.

### Verification
- Login → get token → call `/me` (200) → logout → call `/me` with same token (401)
- Wait for token natural expiry → Redis key auto-removed

---

## Task 1.3 — Fix PDF Export

### Problem
`app/services/report_service.py` exports PDF via `reportlab`. If `reportlab` isn't installed, the fallback at line 509 returns **plain text encoded as bytes**, but the route serves it with `media_type="application/pdf"`. The client receives a `.pdf` file that is actually a text file.

### What To Do

**Option A (Recommended): Make `reportlab` a required dependency.**

Add to `pyproject.toml`:
```toml
dependencies = [
    ...
    "reportlab>=4.0",
]
```

Then any deployment will have reportlab and the fallback path is never hit.

**Option B: If reportlab can't be required, fix the fallback:**

Change the route in `app/routes/reports.py` to check:

```python
@router.post("/export/pdf")
async def export_report_pdf(...):
    try:
        import reportlab  # noqa
        has_reportlab = True
    except ImportError:
        has_reportlab = False
    
    if not has_reportlab:
        raise HTTPException(
            status_code=501,
            detail="PDF export is not available. Install reportlab: pip install reportlab"
        )
    
    # ... proceed with PDF generation
```

This is honest — it tells the caller the feature is unavailable rather than returning garbage.

### Verification
- With reportlab installed: export → valid PDF file
- Without reportlab: export → clear 501 error

---

## Task 1.4 — Replace All `datetime.utcnow()` with `datetime.now(timezone.utc)`

### Problem
`datetime.utcnow()` is deprecated since Python 3.12. It returns a naive datetime (no timezone info), which causes bugs with timezone-aware comparisons. It appears in **every model** and multiple services.

### What To Do

Global find-and-replace across ALL Python files:

```python
# FIND:
datetime.utcnow()

# REPLACE WITH:
datetime.now(timezone.utc)
```

Also add the import where needed:

```python
from datetime import datetime, timezone
```

**Files affected (from audit):**
- `app/models/transaction.py` — `server_default`, `onupdate`
- `app/models/user.py` — `server_default`
- `app/models/budget.py` — `server_default`
- `app/models/goal.py` — `server_default`, `onupdate`
- `app/models/connection.py` — `onupdate`
- `app/models/ml_model.py` — `server_default`
- `app/services/auth_service.py` — token creation
- `app/services/goal_service.py` — progress calculation
- `app/services/advice_generator.py` — date comparisons
- `app/services/report_service.py` — report timestamp
- `app/services/transaction_service.py` — duplicate detection window
- `app/routes/reports.py` — `generated_at` field

**Note on model `server_default`:** If models use `server_default=func.now()` (SQL-side), those are fine. Only Python-side `default=datetime.utcnow` needs changing to `default=lambda: datetime.now(timezone.utc)`.

### Verification
- `grep -r "utcnow" app/` should return 0 results
- All tests should still pass

---

## Task 1.5 — Fix Service Commit Consistency

### Problem
`auth_service.py` calls `await self.db.commit()` directly in `register_user` and `change_password`. All other services use `await self.db.flush()` and leave commit to the caller/middleware. This inconsistency can cause:
- Double commits
- Partial commits if other operations happen in the same request

### What To Do

**In `app/services/auth_service.py`:**

Change `register_user`:
```python
# BEFORE:
self.db.add(user)
await self.db.commit()
await self.db.refresh(user)

# AFTER:
self.db.add(user)
await self.db.flush()
await self.db.refresh(user)
```

Change `change_password`:
```python
# BEFORE:
await self.db.commit()

# AFTER:
await self.db.flush()
```

**Same fix in `app/services/file_import_service.py`** — also calls `commit()` directly.

**Then ensure the request lifecycle commits.** In the database session dependency (`app/database.py`), the `get_db` function should commit on success:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()  # Commit if no exception
        except Exception:
            await session.rollback()
            raise
```

If `get_db` already does this, the flush-only pattern in services is correct and the commit calls in auth_service are redundant/harmful. If `get_db` does NOT commit, then you need to add it.

### Verification
- Register a user → check DB → user exists
- Import transactions → check DB → transactions exist
- Trigger an error mid-request → verify rollback (no partial data)

---

## Task 1.6 — Remove Dead Code in Auth Service

### Problem
`PASSWORD_PATTERN` regex at line 44-46 of `app/services/auth_service.py` is compiled but never used. The actual `validate_password` method uses individual `re.search()` calls.

### What To Do

Remove the dead variable:
```python
# DELETE these lines:
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]"
)
```

Also expand the special character set in `validate_password`:
```python
# BEFORE:
if not re.search(r"[@$!%*?&]", password):

# AFTER:
if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", password):
```

This accepts common special characters that users expect to be valid.

---

## Task 1.7 — Create Missing Schemas

### Problem
Two models have NO corresponding Pydantic schemas:
- `Connection` model (in `app/models/connection.py`) — no schema exists
- `MLModel` model (in `app/models/ml_model.py`) — no schema exists

Additionally, `app/schemas/auth.py` is missing a `UserUpdate` schema.

### What To Do

**Create `app/schemas/connection.py`:**

```python
"""Connection schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    user_id: UUID
    institution_name: str = Field(..., max_length=100)
    institution_id: str = Field(..., max_length=100)
    status: str = Field(default="active", max_length=20)


class ConnectionResponse(BaseModel):
    id: UUID
    user_id: UUID
    institution_name: str
    institution_id: str
    status: str
    last_synced: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class ConnectionUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=20)
    institution_name: Optional[str] = Field(None, max_length=100)
```

**Create `app/schemas/ml_model.py`:**

```python
"""ML Model version schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class MLModelVersionCreate(BaseModel):
    model_type: str = Field(..., max_length=50)
    version: str = Field(..., max_length=20)
    model_path: str = Field(..., max_length=500)
    accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    precision_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    training_samples: Optional[int] = Field(None, ge=0)


class MLModelVersionResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    model_type: str
    version: str
    model_path: str
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    training_samples: Optional[int] = None
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}
```

**Add `UserUpdate` to `app/schemas/auth.py`:**

```python
class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
```

**Fix `created_at` type in `UserResponse`:**

```python
# BEFORE:
created_at: str  # Should be datetime or serialize properly

# AFTER:
created_at: datetime
```

---

## Task 1.8 — Fix Budget Decimal Precision

### Problem
Budget allocations are stored as JSON (floats), but amount comparisons in `budget_service.py` use `Decimal`. Float-to-Decimal round-tripping can produce precision errors (e.g., `0.1 + 0.2 != 0.3`).

### What To Do

In `app/services/budget_service.py`, when reading allocations from the JSONB column, convert via string to avoid float precision issues:

```python
# When reading allocations:
allocations = {
    category: Decimal(str(amount))  # str() conversion avoids float precision loss
    for category, amount in budget.allocations.items()
}
```

Ensure all comparisons use `Decimal(str(...))` conversion, never direct `Decimal(float_value)`.

---

## Task 1.9 — Fix File Import Exporting Deleted Transactions

### Problem
`app/services/file_import_service.py`'s `export_transactions` method doesn't filter by `deleted_at.is_(None)`, so it exports soft-deleted transactions.

### What To Do

Add a filter in the export query:

```python
# In export_transactions method, add to the query:
stmt = stmt.where(Transaction.deleted_at.is_(None))
```

---

## Task 1.10 — Fix Merchant Normalizer Location Regex

### Problem
The location regex in `app/services/merchant_normalizer.py` expects title case (`[A-Z][a-z]+`) but bank statements use ALL-CAPS. "AUSTIN TX" won't match.

### What To Do

Make the regex case-insensitive:

```python
# BEFORE:
LOCATION_PATTERN = re.compile(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+([A-Z]{2})\s*(\d{5})?")

# AFTER:
LOCATION_PATTERN = re.compile(
    r"([A-Za-z]+(?:\s[A-Za-z]+)*)\s+([A-Z]{2})\s*(\d{5})?",
    re.IGNORECASE
)
```

Also normalize the extracted city name to title case for display.

---

## Task 1.11 — Fix `hash()` Cache Key in AI Brain Service

### Problem
`app/services/ai_brain_service.py` line 328 uses `hash(query)` for Redis cache keys. Python's `hash()` is randomized per process (via `PYTHONHASHSEED`), so cache keys differ between restarts and workers.

### What To Do

```python
# BEFORE:
cache_key = f"ai_brain:{mode.value}:{hash(query)}"

# AFTER:
import hashlib
cache_key = f"ai_brain:{mode.value}:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
```

Using SHA-256 (truncated to 16 hex chars) gives a stable, deterministic cache key.

---

## Task 1.12 — Fix LRU Cache Memory Leak in Merchant Database

### Problem
`app/services/merchant_database.py` uses `@lru_cache(maxsize=10000)` on the instance method `_lookup_exact`. `lru_cache` on instance methods holds a strong reference to `self`, preventing garbage collection of the instance.

### What To Do

Use `functools.cached_property` or move the cache to a module-level function:

```python
# Option: Use a module-level function with lru_cache
from functools import lru_cache

@lru_cache(maxsize=10000)
def _cached_exact_lookup(aliases_tuple: tuple, merchant_name: str) -> Optional[dict]:
    """Exact match lookup with caching. aliases_tuple is a frozen hashable."""
    name_lower = merchant_name.lower()
    for alias, merchant_data in aliases_tuple:
        if alias == name_lower:
            return merchant_data
    return None

class MerchantDatabase:
    def _lookup_exact(self, merchant_name: str):
        # Convert to hashable tuple for caching
        return _cached_exact_lookup(
            tuple(self._alias_index.items()),
            merchant_name
        )
```

Alternatively, switch to a simple dict-based cache within the class (no `lru_cache`).

---

## Granular Checklist — Task 1.1 (SecurityMiddleware)

- [x] Create `app/middleware/security.py` file
- [x] Import `InputGuard` and `OutputGuard` from existing middleware files
- [x] Implement `SecurityMiddleware` class extending `BaseHTTPMiddleware`
- [x] Add `dispatch()` method — check POST/PUT/PATCH request bodies with InputGuard
- [x] Return 400 `"Input rejected due to security concerns."` if InputGuard flags threat
- [x] Apply OutputGuard — filter JSON responses on AI endpoint paths
- [x] Define AI response paths set: `/api/ai/chat`, `/api/ai/analyze`, `/api/ai/smart-advice`
- [x] Add try/except around guard calls — don't crash requests on guard errors
- [x] Open `app/main.py`
- [x] Add `from app.middleware.security import SecurityMiddleware` import
- [x] Add `app.add_middleware(SecurityMiddleware)` — after CORS middleware
- [ ] Test: send POST with prompt injection text → expect 400
- [ ] Test: send normal POST request → passes through unchanged
- [ ] Test: AI endpoint response with PII → PII filtered out

---

## Granular Checklist — Task 1.2 (Token Blacklisting)

### Add blacklist methods to AuthService
- [x] Open `app/services/auth_service.py`
- [x] Import `cache_manager` from `app.cache`
- [x] Add `blacklist_token(self, token, expires_in=None)` method
- [x] Decode token to find expiry time
- [x] Set Redis key `blacklist:{token}` with TTL matching token expiry
- [x] Add `is_token_blacklisted(self, token)` method
- [x] Check Redis for `blacklist:{token}` key
- [x] Return `True` if key exists, `False` otherwise

### Wire into auth flow
- [x] Open `app/dependencies.py`
- [x] Add blacklist check BEFORE token validation in `get_current_user()`
- [x] If blacklisted → raise HTTPException 401 "Token has been revoked"
- [x] Open `app/routes/auth.py`
- [x] Update `/logout` endpoint to call `auth_service.blacklist_token(token)`
- [x] Update `/refresh` endpoint to blacklist old access token after issuing new one

### Verification
- [ ] Test: login → get token → call `/me` (200)
- [ ] Test: logout → call `/me` with same token → 401
- [ ] Test: wait for TTL expiry → Redis key auto-removed

---

## Granular Checklist — Task 1.3 (PDF Export Fix)

- [x] Check if `reportlab` is in `pyproject.toml` dependencies
- [x] If not: add `"reportlab>=4.0"` to dependencies list
- [x] If not addable: update `app/routes/reports.py` to return 501 when reportlab unavailable
- [x] Add `try: import reportlab` check in PDF export route
- [x] Return clear error message: "PDF export is not available. Install reportlab."
- [ ] Test: with reportlab installed → export produces valid PDF
- [ ] Test: without reportlab → clear 501 error (not garbage file)

---

## Granular Checklist — Task 1.4 (datetime.utcnow Replacement)

### Models
- [x] Fix `app/models/transaction.py` — replace `datetime.utcnow` with `lambda: datetime.now(timezone.utc)`
- [x] Fix `app/models/user.py` — replace `datetime.utcnow` with `lambda: datetime.now(timezone.utc)`
- [x] Fix `app/models/budget.py` — replace `datetime.utcnow` with `lambda: datetime.now(timezone.utc)`
- [x] Fix `app/models/goal.py` — replace `datetime.utcnow` with `lambda: datetime.now(timezone.utc)`
- [x] Fix `app/models/connection.py` — replace `datetime.utcnow` with `lambda: datetime.now(timezone.utc)`
- [x] Fix `app/models/ml_model.py` — replace `datetime.utcnow` with `lambda: datetime.now(timezone.utc)`
- [x] Add `from datetime import datetime, timezone` import to each model file

### Services
- [x] Fix `app/services/auth_service.py` — token creation timestamps
- [x] Fix `app/services/goal_service.py` — progress calculation
- [x] Fix `app/services/advice_generator.py` — date comparisons
- [x] Fix `app/services/report_service.py` — report timestamp
- [x] Fix `app/services/transaction_service.py` — duplicate detection window

### Routes
- [x] Fix `app/routes/reports.py` — `generated_at` field

### Verification
- [ ] Run `grep -r "utcnow" app/` — should return 0 results
- [ ] All tests still pass

---

## Granular Checklist — Task 1.5 (Commit Consistency)

- [x] Open `app/services/auth_service.py`
- [x] Change `register_user`: replace `await self.db.commit()` with `await self.db.flush()`
- [x] Change `change_password`: replace `await self.db.commit()` with `await self.db.flush()`
- [x] Open `app/services/file_import_service.py`
- [x] Replace `await self.db.commit()` with `await self.db.flush()`
- [x] Open `app/database.py` → `get_db()` function
- [x] Verify it has `await session.commit()` on success
- [x] Verify it has `await session.rollback()` in except block
- [x] If missing: add commit-on-success / rollback-on-error pattern
- [ ] Test: register user → check DB → user exists
- [ ] Test: import transactions → check DB → transactions exist
- [ ] Test: trigger error mid-request → verify no partial data

---

## Granular Checklist — Task 1.6 (Dead Code Removal)

- [x] Open `app/services/auth_service.py`
- [x] Delete `PASSWORD_PATTERN = re.compile(...)` declaration (lines 44-46)
- [x] Find `validate_password` method
- [x] Expand special character regex from `[@$!%*?&]` to `[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~\`]`
- [ ] Verify: registration with extended special chars works

---

## Granular Checklist — Task 1.7 (Missing Schemas)

### Connection Schema
- [x] Create `app/schemas/connection.py` file
- [x] Add `ConnectionCreate` schema with required fields
- [x] Add `ConnectionResponse` schema with `model_config = {"from_attributes": True}`
- [x] Add `ConnectionUpdate` schema with all optional fields

### ML Model Schema
- [x] Create `app/schemas/ml_model.py` file
- [x] Add `MLModelVersionCreate` schema with validation (ge=0.0, le=1.0 for scores)
- [x] Add `MLModelVersionResponse` schema with `model_config = {"from_attributes": True}`

### Auth Schema Updates
- [x] Open `app/schemas/auth.py`
- [x] Add `UserUpdate` schema (optional `full_name`, optional `email`)
- [x] Fix `created_at` type in `UserResponse` — change from `str` to `datetime`
- [ ] Verify: all new schemas can be imported without errors

---

## Granular Checklist — Task 1.8 (Decimal Precision)

- [x] Open `app/services/budget_service.py`
- [x] Find all places where allocations are read from JSONB
- [x] Convert float values via `Decimal(str(amount))` — NOT `Decimal(float_value)`
- [x] Ensure all allocation comparisons use `Decimal(str(...))` conversion
- [ ] Test: create budget with allocation 0.1 + 0.2 — should equal 0.3 exactly

---

## Granular Checklist — Task 1.9 (Soft-Delete Export Bug)

- [x] Open `app/services/file_import_service.py`
- [x] Find `export_transactions` method
- [x] Add `.where(Transaction.deleted_at.is_(None))` to the query
- [ ] Test: soft-delete a transaction → export → ensure deleted transaction is NOT in export

---

## Granular Checklist — Task 1.10 (Location Regex)

- [x] Open `app/services/merchant_normalizer.py`
- [x] Find `LOCATION_PATTERN` regex
- [x] Change from `[A-Z][a-z]+` to `[A-Za-z]+` (or add `re.IGNORECASE`)
- [x] Add `re.IGNORECASE` flag to `re.compile()`
- [x] Normalize extracted city name to title case for display
- [ ] Test: input "AUSTIN TX" → matches correctly
- [ ] Test: input "Austin TX" → still matches correctly

---

## Granular Checklist — Task 1.11 (Hash Cache Key)

- [x] Open `app/services/ai_brain_service.py`
- [x] Find `cache_key = f"ai_brain:{mode.value}:{hash(query)}"`
- [x] Add `import hashlib` at top of file
- [x] Change to `hashlib.sha256(query.encode()).hexdigest()[:16]`
- [ ] Test: same query → same cache key across process restarts

---

## Granular Checklist — Task 1.12 (LRU Cache Leak)

- [x] Open `app/services/merchant_database.py`
- [x] Find `@lru_cache(maxsize=10000)` on `_lookup_exact` instance method
- [x] Move cache to module-level function (not bound to `self`)
- [x] Or replace `@lru_cache` with a simple `dict`-based cache within the class
- [ ] Verify: MerchantDatabase instances can be garbage collected

---

## Final P1 Validation

- [ ] Run ALL tests (`pytest tests/ -v`)
- [ ] All tests pass
- [ ] `grep -r "utcnow" app/` → 0 results
- [ ] SecurityMiddleware registered and working
- [ ] Logout actually invalidates tokens
- [ ] No dead code remaining in auth_service
- [ ] All models have corresponding schemas
