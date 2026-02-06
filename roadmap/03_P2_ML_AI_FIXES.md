# Phase 2 — ML & AI Fixes

> **Can run in parallel with P3 and P4 after P0 is done**  
> **Estimated Effort:** 5-7 days  
> **Status:** ~13% complete — most ML/AI tasks are not yet started  
> **Covers:** Training data quality, preprocessing mismatch, ARIMA performance, RAG implementation, AI Brain runtime fixes, category taxonomy unification

---

## Task 2.1 — Unify Category Taxonomy Across All Modules

### Problem
Different parts of the codebase use different category names for the same concept:

| Module | Categories Used |
|--------|----------------|
| `app/ml/training_data.py` | Groceries, Dining, Transportation, Entertainment, Shopping, Healthcare, Utilities, Rent/Mortgage, Insurance, Education, Personal Care, Gifts/Donations, Travel, Salary, Freelance, Investment, Other Income |
| `ai_brain/inference/validation.py` | Groceries, Fast Food, Coffee & Beverages, Gas & Fuel, Shopping & Retail |
| `app/services/rag_prompts.py` | Different list in VALID_CATEGORIES |
| `models/categories.json` | Yet another list |

This means cross-validation between ML and AI Brain always fails, and the validation layer flags correct predictions as wrong.

### What To Do

**Step 1: Create a single source of truth** — `app/constants/categories.py`:

```python
"""
Single source of truth for all transaction categories.
Every module MUST import from here. Do NOT define categories elsewhere.
"""

# Primary categories (top-level)
CATEGORIES = {
    "Groceries": {"aliases": ["grocery", "supermarket", "food store"]},
    "Dining": {"aliases": ["restaurant", "fast food", "coffee", "cafe", "bar"]},
    "Transportation": {"aliases": ["gas", "fuel", "uber", "lyft", "transit", "parking", "rideshare"]},
    "Entertainment": {"aliases": ["movies", "streaming", "gaming", "concerts", "sports"]},
    "Shopping": {"aliases": ["retail", "clothing", "electronics", "amazon", "online shopping"]},
    "Healthcare": {"aliases": ["medical", "pharmacy", "doctor", "dental", "vision"]},
    "Utilities": {"aliases": ["electric", "water", "gas bill", "internet", "phone"]},
    "Housing": {"aliases": ["rent", "mortgage", "property tax", "maintenance"]},
    "Insurance": {"aliases": ["health insurance", "car insurance", "life insurance"]},
    "Education": {"aliases": ["tuition", "books", "courses", "training"]},
    "Personal Care": {"aliases": ["salon", "spa", "gym", "fitness"]},
    "Gifts & Donations": {"aliases": ["charity", "gift", "donation"]},
    "Travel": {"aliases": ["hotel", "flight", "airfare", "vacation"]},
    "Subscriptions": {"aliases": ["netflix", "spotify", "membership", "subscription"]},
    "Salary": {"aliases": ["payroll", "direct deposit", "wages"]},
    "Freelance Income": {"aliases": ["freelance", "contract", "consulting"]},
    "Investment Income": {"aliases": ["dividend", "interest", "capital gains"]},
    "Other Income": {"aliases": ["refund", "cashback", "reimbursement"]},
    "Uncategorized": {"aliases": []},
}

VALID_CATEGORIES = list(CATEGORIES.keys())

EXPENSE_CATEGORIES = [c for c in VALID_CATEGORIES if c not in {"Salary", "Freelance Income", "Investment Income", "Other Income"}]

INCOME_CATEGORIES = ["Salary", "Freelance Income", "Investment Income", "Other Income"]

# Mapping from any alias/variant to the canonical category name
CATEGORY_ALIASES = {}
for category, info in CATEGORIES.items():
    CATEGORY_ALIASES[category.lower()] = category
    for alias in info["aliases"]:
        CATEGORY_ALIASES[alias.lower()] = category
```

**Step 2: Update ALL modules to import from this file:**

- `app/ml/training_data.py` → use `VALID_CATEGORIES` from constants
- `app/ml/categorization_engine.py` → import `VALID_CATEGORIES`
- `ai_brain/inference/validation.py` → import `VALID_CATEGORIES` and `CATEGORY_ALIASES`
- `app/services/rag_prompts.py` → import `VALID_CATEGORIES`
- `app/services/ai_validation.py` → import from constants
- `app/routes/predictions.py` → validate `category` param against `VALID_CATEGORIES`
- `models/categories.json` → regenerate from `CATEGORIES` dict or replace usage with imports

**Step 3: Update `ai_brain/inference/validation.py`:**

Replace the hardcoded `CATEGORY_HIERARCHY` with imports from `app.constants.categories`. Fix the `CATEGORY_TO_PARENT` reverse lookup that uses inconsistent casing.

### Verification
- `grep -rn "VALID_CATEGORIES\|valid_categories" app/ ai_brain/` — all point to `app.constants.categories`
- No hardcoded category lists remain in any file
- ML categorization and AI Brain validation use the same taxonomy

---

## Task 2.2 — Fix Train/Serve Preprocessing Mismatch

### Problem
Training uses `preprocess_text()` from `app/ml/training_data.py`. Inference uses `preprocess_transaction()` from `app/ml/text_preprocessor.py`. They are **different functions** — the training preprocessor lacks abbreviation expansion, store-number stripping, etc. This mismatch hurts accuracy.

### What To Do

**Eliminate `preprocess_text()` from `training_data.py` entirely.** Use the same preprocessor everywhere:

In `app/ml/training_data.py`:
```python
# BEFORE:
def preprocess_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# AFTER: Remove this function entirely. Import from text_preprocessor:
from app.ml.text_preprocessor import preprocess_transaction

# In generate_training_data(), change:
#   processed = preprocess_text(desc)
# to:
#   processed = preprocess_transaction(desc)
```

In `app/ml/train_model.py`:
```python
# Change:
from app.ml.training_data import preprocess_text
# To:
from app.ml.text_preprocessor import preprocess_transaction as preprocess_text
```

### After Fixing
**Retrain the model** by running:
```bash
python -m app.ml.train_model
```

This will regenerate `models/global_categorization_model.pkl` with the correct preprocessing.

### Verification
- `grep -rn "preprocess_text" app/ml/` should only show the import alias, not a local function definition
- Retrained model accuracy should be similar or better (since training and inference now use the same preprocessing)

---

## Task 2.3 — Improve Training Data (Replace Synthetic with Real)

### Problem
The ML model is trained on ~170 hand-written synthetic descriptions, inflated 6x by variations that collapse after preprocessing. This is too small for production accuracy.

### What To Do

**Step 1: Create a proper training data file** — `data/training_transactions.json`:

Expand to at least 1,000 unique transaction descriptions across all categories. Sources:
- Real bank statement formats (anonymized)
- Common merchant names from `data/merchants.json`
- Variations with amounts, dates, location codes

Structure:
```json
[
    {"description": "WHOLEFDS MKT 10445 AUSTIN TX", "category": "Groceries"},
    {"description": "UBER TRIP HELP.UBER.COM", "category": "Transportation"},
    {"description": "NETFLIX.COM", "category": "Subscriptions"},
    ...
]
```

**Step 2: Update `app/ml/training_data.py`:**

```python
import json
from pathlib import Path

def load_training_data() -> list[tuple[str, str]]:
    """Load training data from JSON file."""
    data_path = Path("data/training_transactions.json")
    if data_path.exists():
        with open(data_path) as f:
            records = json.load(f)
        return [(r["description"], r["category"]) for r in records]
    
    # Fallback to synthetic if file not found
    return generate_synthetic_data()
```

**Step 3: Add data augmentation** that actually helps:

```python
def augment_data(data: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Augment training data with meaningful variations."""
    augmented = list(data)
    for desc, cat in data:
        # Add with random store numbers
        augmented.append((f"{desc} #{''.join(random.choices('0123456789', k=4))}", cat))
        # Add with location codes
        augmented.append((f"{desc} {''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=2))}", cat))
        # Add with date references
        augmented.append((f"{desc} 01/15", cat))
    return augmented
```

**Step 4: Retrain and evaluate:**

```bash
python -m app.ml.train_model
```

Target metrics:
- Accuracy ≥ 85% on test set
- Per-category precision ≥ 70% for categories with 20+ samples
- F1 score ≥ 0.80

### Verification
- Training data file exists with 1000+ entries
- Model metrics file shows improved accuracy
- Manual test: categorize 20 real-world bank descriptions → ≥16 correct

---

## Task 2.4 — Cache ARIMA Parameters in Prediction Engine

### Problem
`app/ml/prediction_engine.py` grid-searches 50+ ARIMA (p,d,q) parameter combinations on **every API call**. This makes a single forecast request take minutes, making it unusable as a web API.

### What To Do

**Step 1: Cache ARIMA parameters per user+category:**

```python
import hashlib
import json

class PredictionEngine:
    def __init__(self, db):
        self.db = db
        self._arima_param_cache = {}  # In-memory cache
    
    def _get_cache_key(self, user_id, category, data_hash):
        """Generate cache key for ARIMA params."""
        return f"{user_id}:{category}:{data_hash}"
    
    def _data_hash(self, series):
        """Hash the time series data to detect when refit is needed."""
        data_str = series.to_json()
        return hashlib.md5(data_str.encode()).hexdigest()[:8]
    
    def _find_best_arima_params(self, series, user_id, category):
        """Find best ARIMA params with caching."""
        d_hash = self._data_hash(series)
        cache_key = self._get_cache_key(user_id, category, d_hash)
        
        if cache_key in self._arima_param_cache:
            return self._arima_param_cache[cache_key]
        
        # Grid search (expensive, only done once per data change)
        best_params = self._grid_search_arima(series)
        self._arima_param_cache[cache_key] = best_params
        return best_params
```

**Step 2: Reduce grid search space:**

```python
# BEFORE: max_p=5, max_d=2, max_q=5 → 50+ combinations
# AFTER: Reasonable defaults
ARIMA_SEARCH_SPACE = [
    (1, 1, 1), (1, 1, 0), (0, 1, 1),  # Common defaults
    (2, 1, 1), (1, 1, 2), (2, 1, 2),  # Slightly more complex
    (0, 1, 0), (1, 0, 0), (0, 0, 1),  # Simple models
]
```

This reduces from 50+ to 9 fits — ~5x faster.

**Step 3: Add Redis-level caching for forecasts:**

In `app/routes/predictions.py`:
```python
from app.cache import cache_manager

@router.get("/forecast")
async def get_expense_forecasts(...):
    cache_key = f"forecast:{user_id}:{periods}:{lookback_days}"
    cached = await cache_manager.get(cache_key)
    if cached:
        return cached
    
    # ... generate forecast ...
    
    await cache_manager.set(cache_key, result, ttl=3600)  # 1 hour cache
    return result
```

**Step 4: Fix the misleading MAPE accuracy metric:**

```python
# BEFORE:
mape = np.mean(np.abs((actual - in_sample_pred) / (actual + 1))) * 100

# AFTER: Use only non-zero days for MAPE
non_zero_mask = actual > 0
if non_zero_mask.sum() > 0:
    mape = np.mean(np.abs((actual[non_zero_mask] - in_sample_pred[non_zero_mask]) / actual[non_zero_mask])) * 100
else:
    mape = None  # Can't compute MAPE with all-zero actuals
```

### Verification
- First forecast call: slow (grid search happens)
- Second call with same data: fast (cached params)
- Third call within 1 hour: instant (Redis cached result)
- MAPE metric accurately reflects prediction quality

---

## Task 2.5 — Fix AI Brain Runtime Crashes

### Problem
`ai_brain/inference/brain_service.py` calls `confidence_calc.should_add_disclaimer(confidence, mode.value)` passing `(float, str)`, but `confidence.py`'s `should_add_disclaimer(self, result: ConfidenceResult)` expects a `ConfidenceResult` object. This crashes with `TypeError` at runtime.

Same bug for `get_disclaimer_text`.

### What To Do

**Option A: Fix the caller to construct a `ConfidenceResult`:**

In `ai_brain/inference/brain_service.py`, lines 257-260:

```python
# BEFORE:
if confidence_calc.should_add_disclaimer(confidence, mode.value):
    disclaimer = confidence_calc.get_disclaimer_text(confidence, mode.value)

# AFTER:
from ai_brain.inference.confidence import ConfidenceResult, ConfidenceLevel

# Determine confidence level
if confidence >= 0.8:
    level = ConfidenceLevel.HIGH
elif confidence >= 0.6:
    level = ConfidenceLevel.MEDIUM  
elif confidence >= 0.4:
    level = ConfidenceLevel.LOW
else:
    level = ConfidenceLevel.VERY_LOW

confidence_result = ConfidenceResult(
    score=confidence,
    level=level,
    details={"mode": mode.value},
)

if confidence_calc.should_add_disclaimer(confidence_result):
    disclaimer = confidence_calc.get_disclaimer_text(confidence_result)
    response_text += f"\n\n{disclaimer}"
```

### Additional AI Brain Fixes

**Fix 1: `max_length` too restrictive**
```python
# BEFORE (brain_service.py):
max_length = 2048 - self.max_new_tokens

# AFTER: Qwen2.5-3B supports 32K context
max_length = min(8192, 32768 - self.max_new_tokens)
```

**Fix 2: Deprecated `asyncio.get_event_loop()`**
```python
# BEFORE:
loop = asyncio.get_event_loop()

# AFTER:
loop = asyncio.get_running_loop()
```

**Fix 3: `detect_mode` regex false positives**
```python
# BEFORE:
if re.match(r"^[A-Z]{2,}", query):  # Matches any 2+ uppercase letters

# AFTER: Require specific transaction-like patterns
if re.match(r"^[A-Z]{3,}\s*(#|\*|0\d)", query):  # e.g., "AMZN #123", "SQ *COFFEE"
```

### Verification
- If AI Brain HTTP server is running: confidence-based disclaimer works without TypeError
- If not running: fallback path still works (unaffected)

---

## Task 2.6 — Implement Real RAG (Replace Mock Data)

### Problem
`ai_brain/inference/rag_retriever.py` returns hardcoded mock data for every retrieval method. The `DatabaseRAG` subclass overrides one method but calls `super()` which returns mocks anyway. No real database queries exist.

### What To Do

**Rewrite `rag_retriever.py` to query the actual database:**

```python
class DatabaseRAGRetriever(RAGRetriever):
    """RAG retriever that queries the actual PostgreSQL database."""
    
    def __init__(self, db: AsyncSession, user_id: UUID):
        super().__init__()
        self.db = db
        self.user_id = user_id
    
    async def _get_spending_summary(self, months: int = 3) -> dict:
        """Get actual spending summary from transaction table."""
        from app.models.transaction import Transaction
        from sqlalchemy import func, case
        from datetime import datetime, timezone, timedelta
        
        start_date = datetime.now(timezone.utc) - timedelta(days=months * 30)
        
        stmt = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count().label("count"),
                func.avg(Transaction.amount).label("avg"),
            )
            .where(
                Transaction.user_id == self.user_id,
                Transaction.created_at >= start_date,
                Transaction.deleted_at.is_(None),
                Transaction.transaction_type == "EXPENSE",
            )
            .group_by(Transaction.category)
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        return {
            "period_months": months,
            "categories": {
                row.category: {
                    "total": float(row.total),
                    "count": row.count,
                    "average": float(row.avg),
                }
                for row in rows
            },
            "total_spending": sum(float(row.total) for row in rows),
        }
    
    async def _get_recent_transactions(self, limit: int = 20) -> list:
        """Get actual recent transactions."""
        from app.models.transaction import Transaction
        
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == self.user_id,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.date.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()
        
        return [
            {
                "description": t.description,
                "amount": float(t.amount),
                "category": t.category,
                "date": t.date.isoformat(),
                "type": t.transaction_type,
            }
            for t in transactions
        ]
    
    async def _get_budgets(self) -> list:
        """Get actual user budgets."""
        from app.models.budget import Budget
        
        stmt = select(Budget).where(Budget.user_id == self.user_id)
        result = await self.db.execute(stmt)
        budgets = result.scalars().all()
        
        return [
            {
                "name": b.name,
                "amount": float(b.amount),
                "period_start": b.period_start.isoformat(),
                "period_end": b.period_end.isoformat(),
                "allocations": b.allocations or {},
            }
            for b in budgets
        ]
    
    async def _get_goals(self) -> list:
        """Get actual user financial goals."""
        from app.models.goal import FinancialGoal
        
        stmt = select(FinancialGoal).where(FinancialGoal.user_id == self.user_id)
        result = await self.db.execute(stmt)
        goals = result.scalars().all()
        
        return [
            {
                "name": g.name,
                "target": float(g.target_amount),
                "current": float(g.current_amount),
                "deadline": g.deadline.isoformat() if g.deadline else None,
                "status": g.status,
            }
            for g in goals
        ]
```

**Update `app/services/rag_context.py`** to use the database retriever:

```python
# Pass db session and user_id when building RAG context
async def build_context(self, query: str, db: AsyncSession, user_id: UUID):
    retriever = DatabaseRAGRetriever(db, user_id)
    spending = await retriever._get_spending_summary()
    transactions = await retriever._get_recent_transactions()
    budgets = await retriever._get_budgets()
    goals = await retriever._get_goals()
    ...
```

### Verification
- Chat with AI Brain → context includes real user transactions, not mock data
- Empty user → context shows empty spending (not hardcoded $450 groceries)
- Semantic search still works (on real data now)

---

## Task 2.7 — Wire AI Brain Templates Into Pipeline

### Problem
`ai_brain/inference/templates.py` has well-written response formatting code but it's **never called** by `brain_service.py`. Raw LLM output is returned directly.

### What To Do

In `ai_brain/inference/brain_service.py`, after generating a response:

```python
from ai_brain.inference.templates import ResponseFormatter

formatter = ResponseFormatter()

# After getting raw_response from the model:
if mode == AIBrainMode.CHAT:
    formatted = formatter.format_chat_response(raw_response)
elif mode == AIBrainMode.ANALYZE:
    formatted = formatter.format_analysis_response(raw_response)
elif mode == AIBrainMode.PARSE:
    formatted = formatter.format_parse_response(raw_response)
else:
    formatted = raw_response

return formatted
```

### Verification
- Chat responses have structured sections (greeting, summary, recommendations)
- Analysis responses have financial disclaimers
- Parse responses return structured category/amount/merchant data

---

## Task 2.8 — Fix AI Validation Cross-Validation

### Problem
- `ai_validation_service` singleton is created with `ml_service=None` → cross-validation always uses empty predictions
- `CATEGORY_HIERARCHY` keys don't match `VALID_CATEGORIES`
- `CATEGORY_TO_PARENT` built with `.lower()` keys but checked against original keys

### What To Do

**Step 1: Wire ML service into validation singleton:**

In `app/services/ai_validation.py`, change module-level initialization:

```python
# BEFORE:
ai_validation_service = AIValidationService()

# AFTER: Lazy initialization with ML service
_ai_validation_service = None

def get_ai_validation_service(ml_service=None):
    global _ai_validation_service
    if _ai_validation_service is None:
        _ai_validation_service = AIValidationService(ml_service=ml_service)
    return _ai_validation_service
```

**Step 2: Import categories from the unified constants (Task 2.1):**

```python
from app.constants.categories import VALID_CATEGORIES, CATEGORY_ALIASES
```

**Step 3: Fix the case-sensitivity bug in `CATEGORY_TO_PARENT`:**

```python
# BEFORE: inconsistent casing
CATEGORY_TO_PARENT = {}
for parent, children in CATEGORY_HIERARCHY.items():
    for child in children:
        CATEGORY_TO_PARENT[child.lower()] = parent

# In _check_agreement:
if ai_category.lower() in CATEGORY_TO_PARENT:  # lowercase lookup
    parent = CATEGORY_TO_PARENT[ai_category.lower()]
    if parent.lower() in ml_category.lower():  # This works
        ...

# But later:
if ai_category in CATEGORY_HIERARCHY:  # This is NOT lowercased — BUG
```

Fix: Normalize everything to lowercase consistently.

### Verification
- Cross-validation actually compares ML vs AI predictions
- Category hierarchy checks work regardless of casing

---

## Task 2.9 — Feedback Collector: Add Deduplication + DB Persistence

### Problem
- Same user can submit corrections for the same transaction multiple times, inflating consensus count
- All corrections stored in memory + JSON files (not database-backed)
- `asyncio.create_task(self._save_data())` is fire-and-forget — data loss on crash

### What To Do

**Step 1: Add deduplication:**

```python
async def record_correction(self, user_id, transaction_id, original, corrected, merchant):
    # Check for existing correction from this user for this transaction
    dedup_key = f"{user_id}:{transaction_id}"
    if dedup_key in self._submitted_corrections:
        # Update existing instead of creating new
        old = self._submitted_corrections[dedup_key]
        # Remove old correction from counts
        ...
    self._submitted_corrections[dedup_key] = corrected
    ...
```

**Step 2: Validate corrected category:**

```python
from app.constants.categories import VALID_CATEGORIES

if corrected_category not in VALID_CATEGORIES:
    raise ValueError(f"Invalid category: {corrected_category}. Must be one of {VALID_CATEGORIES}")
```

**Step 3 (Future): Migrate to database storage.** Create a `Correction` model:

```python
class Correction(Base):
    __tablename__ = "corrections"
    id = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    transaction_id = mapped_column(UUID, ForeignKey("transactions.id"), nullable=False)
    original_category = mapped_column(String(50), nullable=False)
    corrected_category = mapped_column(String(50), nullable=False)
    merchant_name = mapped_column(String(200))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("user_id", "transaction_id", name="uq_user_transaction_correction"),
    )
```

---

## Granular Checklist — Task 2.1 (Unified Category Taxonomy)

### Create single source of truth
- [ ] Create `app/constants/` directory
- [ ] Create `app/constants/__init__.py`
- [ ] Create `app/constants/categories.py`
- [ ] Define `CATEGORIES` dict with all category names and aliases
- [ ] Define `VALID_CATEGORIES` list from `CATEGORIES.keys()`
- [ ] Define `EXPENSE_CATEGORIES` (exclude income categories)
- [ ] Define `INCOME_CATEGORIES` list
- [ ] Build `CATEGORY_ALIASES` reverse lookup (alias → canonical name)

### Update all modules to use single source
- [ ] Update `app/ml/training_data.py` — import `VALID_CATEGORIES` from constants
- [ ] Remove hardcoded category list from `training_data.py`
- [ ] Update `app/ml/categorization_engine.py` — import `VALID_CATEGORIES` from constants
- [ ] Remove hardcoded category list from `categorization_engine.py`
- [ ] Update `ai_brain/inference/validation.py` — import from constants
- [ ] Remove hardcoded `CATEGORY_HIERARCHY` from `validation.py`
- [ ] Update `app/services/rag_prompts.py` — import from constants
- [ ] Remove hardcoded `VALID_CATEGORIES` from `rag_prompts.py`
- [ ] Update `app/services/ai_validation.py` — import from constants
- [ ] Update `app/routes/predictions.py` — validate category param against imported list

### Verification
- [ ] `grep -rn "VALID_CATEGORIES\|valid_categories" app/ ai_brain/` — all point to `app.constants.categories`
- [ ] No hardcoded category lists remain in any file
- [ ] ML categorization and AI Brain use same taxonomy

---

## Granular Checklist — Task 2.2 (Train/Serve Preprocessing Mismatch)

- [ ] Open `app/ml/training_data.py`
- [ ] Find `preprocess_text()` function
- [ ] Delete the entire function
- [ ] Add `from app.ml.text_preprocessor import preprocess_transaction` import
- [ ] In `generate_training_data()`, replace `preprocess_text(desc)` with `preprocess_transaction(desc)`
- [ ] Open `app/ml/train_model.py`
- [ ] Change import from `preprocess_text` to `preprocess_transaction`
- [ ] Verify: `grep -rn "preprocess_text" app/ml/` returns no function definition
- [ ] Retrain model: `python -m app.ml.train_model`
- [ ] Verify: retrained model accuracy is similar or better

---

## Granular Checklist — Task 2.3 (Training Data Expansion)

- [ ] Create `data/training_transactions.json` file
- [ ] Add 200+ "Groceries" descriptions (real bank statement formats)
- [ ] Add 100+ "Dining" descriptions
- [ ] Add 100+ "Transportation" descriptions
- [ ] Add 100+ "Entertainment" descriptions
- [ ] Add 100+ "Shopping" descriptions
- [ ] Add 80+ "Healthcare" descriptions
- [ ] Add 80+ "Utilities" descriptions
- [ ] Add 60+ "Housing" descriptions
- [ ] Add 50+ "Insurance" descriptions
- [ ] Add 50+ "Education" descriptions
- [ ] Add 40+ "Personal Care" descriptions
- [ ] Add 40+ "Gifts & Donations" descriptions
- [ ] Add 40+ "Travel" descriptions
- [ ] Add 40+ "Subscriptions" descriptions
- [ ] Add 50+ income descriptions (Salary, Freelance, Investment, Other)
- [ ] Total count ≥ 1,000 unique descriptions
- [ ] Update `app/ml/training_data.py` — add `load_training_data()` to load from JSON
- [ ] Add fallback to synthetic data if JSON file not found
- [ ] Add data augmentation function (store numbers, location codes, dates)
- [ ] Retrain model with new data
- [ ] Verify: accuracy ≥ 85% on test set
- [ ] Verify: per-category precision ≥ 70% (categories with 20+ samples)
- [ ] Verify: manual test — categorize 20 real-world descriptions → ≥16 correct

---

## Granular Checklist — Task 2.4 (ARIMA Performance)

### Parameter caching
- [ ] Open `app/ml/prediction_engine.py`
- [ ] Add in-memory `_arima_param_cache` dict to `PredictionEngine.__init__`
- [ ] Create `_get_cache_key(user_id, category, data_hash)` method
- [ ] Create `_data_hash(series)` method using MD5 of series data
- [ ] Create `_find_best_arima_params(series, user_id, category)` with cache lookup
- [ ] If cache hit → return cached params (skip grid search)
- [ ] If cache miss → grid search then cache result

### Reduce search space
- [ ] Find ARIMA parameter grid (max_p, max_d, max_q)
- [ ] Replace 50+ combinations with 9 common defaults
- [ ] Define `ARIMA_SEARCH_SPACE` as explicit list of (p,d,q) tuples

### Redis result caching
- [ ] Open `app/routes/predictions.py`
- [ ] Import `cache_manager` from `app.cache`
- [ ] Add Redis cache check at start of `get_expense_forecasts`
- [ ] Cache key: `forecast:{user_id}:{periods}:{lookback_days}`
- [ ] Cache TTL: 3600 seconds (1 hour)
- [ ] Return cached result if available
- [ ] Cache new result after computation

### Fix MAPE metric
- [ ] Find MAPE calculation in prediction engine
- [ ] Add `non_zero_mask = actual > 0` filter
- [ ] Only compute MAPE on non-zero days
- [ ] Return `None` for MAPE if all actuals are zero

### Verification
- [ ] Test: first forecast call → slow (grid search runs)
- [ ] Test: second call with same data → fast (cached params)
- [ ] Test: same call within 1 hour → instant (Redis cached)

---

## Granular Checklist — Task 2.5 (AI Brain Runtime Fixes)

### Fix confidence API mismatch
- [ ] Open `ai_brain/inference/brain_service.py`
- [ ] Find `confidence_calc.should_add_disclaimer(confidence, mode.value)` call
- [ ] Import `ConfidenceResult`, `ConfidenceLevel` from `confidence.py`
- [ ] Create `ConfidenceResult` object from `(float, str)` before calling
- [ ] Determine `ConfidenceLevel` from score (HIGH ≥0.8, MEDIUM ≥0.6, LOW ≥0.4, else VERY_LOW)
- [ ] Fix `should_add_disclaimer()` call to pass `ConfidenceResult` object
- [ ] Fix `get_disclaimer_text()` call to pass `ConfidenceResult` object
- [ ] Append disclaimer to response text if applicable

### Fix max_length
- [ ] Find `max_length = 2048 - self.max_new_tokens`
- [ ] Change to `max_length = min(8192, 32768 - self.max_new_tokens)` (Qwen2.5-3B supports 32K)

### Fix deprecated asyncio call
- [ ] Find `loop = asyncio.get_event_loop()`
- [ ] Change to `loop = asyncio.get_running_loop()`

### Fix detect_mode regex
- [ ] Find regex `r"^[A-Z]{2,}"` in detect_mode
- [ ] Change to `r"^[A-Z]{3,}\s*(#|\*|0\d)"` — require transaction-like patterns
- [ ] Test: "AMZN #123" → detected as parse mode
- [ ] Test: "How much" → NOT detected as parse mode

---

## Granular Checklist — Task 2.6 (Real RAG Implementation)

### Database RAG retriever
- [ ] Open `ai_brain/inference/rag_retriever.py`
- [ ] Create `DatabaseRAGRetriever` class with `db` and `user_id` params
- [ ] Implement `_get_spending_summary()` — query Transaction table grouped by category
- [ ] Filter by `user_id`, last N months, non-deleted, EXPENSE type
- [ ] Return total per category, count, average
- [ ] Implement `_get_recent_transactions()` — query last 20 transactions
- [ ] Return description, amount, category, date, type
- [ ] Implement `_get_budgets()` — query all user budgets
- [ ] Return name, amount, period, allocations
- [ ] Implement `_get_goals()` — query all user financial goals
- [ ] Return name, target, current, deadline, status

### Wire into context builder
- [ ] Open `app/services/rag_context.py`
- [ ] Import `DatabaseRAGRetriever`
- [ ] Update `build_context()` to accept `db` session and `user_id`
- [ ] Instantiate DatabaseRAGRetriever with real DB session
- [ ] Call all retriever methods and build context string

### Verification
- [ ] Test: chat with AI Brain → context includes real user transactions
- [ ] Test: empty user → context shows empty spending (not mock data)
- [ ] Test: semantic search works on real data

---

## Granular Checklist — Task 2.7 (Wire Templates)

- [ ] Open `ai_brain/inference/brain_service.py`
- [ ] Import `ResponseFormatter` from `templates.py`
- [ ] Instantiate `formatter = ResponseFormatter()`
- [ ] After generating raw response, format based on mode:
  - [ ] CHAT mode → `formatter.format_chat_response(raw_response)`
  - [ ] ANALYZE mode → `formatter.format_analysis_response(raw_response)`
  - [ ] PARSE mode → `formatter.format_parse_response(raw_response)`
  - [ ] Default → return raw response
- [ ] Test: chat responses have structured sections
- [ ] Test: analysis responses have financial disclaimers
- [ ] Test: parse responses return structured category/amount/merchant

---

## Granular Checklist — Task 2.8 (AI Validation Fixes)

### Wire ML service
- [ ] Open `app/services/ai_validation.py`
- [ ] Find module-level `ai_validation_service = AIValidationService()` singleton
- [ ] Replace with lazy initialization function `get_ai_validation_service(ml_service=None)`
- [ ] Use global variable pattern for singleton
- [ ] Pass ML service on first initialization

### Fix category hierarchy
- [ ] Import categories from `app.constants.categories` (unified source)
- [ ] Replace hardcoded `CATEGORY_HIERARCHY` with imported constants
- [ ] Fix `CATEGORY_TO_PARENT` — ensure consistent casing (all lowercase keys)
- [ ] Fix `_check_agreement` — normalize all category lookups to lowercase
- [ ] Verify: cross-validation compares ML vs AI predictions correctly
- [ ] Verify: hierarchy checks work regardless of casing

---

## Granular Checklist — Task 2.9 (Feedback Collector)

### Deduplication
- [ ] Open `app/services/feedback_collector.py`
- [ ] Add `_submitted_corrections` dict for dedup tracking
- [ ] Create dedup key: `f"{user_id}:{transaction_id}"`
- [ ] Check for existing correction before recording new one
- [ ] If exists: update existing instead of creating duplicate
- [ ] Remove old correction from consensus counts before updating

### Category validation
- [ ] Import `VALID_CATEGORIES` from `app.constants.categories`
- [ ] Validate `corrected_category` against `VALID_CATEGORIES` before recording
- [ ] Raise `ValueError` for invalid categories

### Verification
- [ ] Test: submit same correction twice → only one recorded
- [ ] Test: submit correction with invalid category → error
- [ ] Test: submit correction with valid category → success

---

## Final P2 Validation

- [ ] Retrained ML model exists at `models/global_categorization_model.pkl`
- [ ] Model accuracy ≥ 85% on test set
- [ ] `grep -rn "preprocess_text" app/ml/` → no function definitions
- [ ] All modules import categories from `app.constants.categories`
- [ ] Forecast endpoint responds in < 5 seconds (cached)
- [ ] AI Brain confidence calls don't crash with TypeError
- [ ] RAG returns real user data, not mock data
- [ ] End-to-end: transaction → categorization → AI fallback → correction → retrain works
