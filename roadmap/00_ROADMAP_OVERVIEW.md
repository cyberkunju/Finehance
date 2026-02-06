# FINEHANCE — Production Perfection Roadmap

> **How to use:** Check off boxes `- [x]` as you complete each item. Every small step has its own checkbox.
>
> **Last verified against codebase:** February 2026

---

## Current State (Post-Audit, Feb 2026)

| Area | Status | Rating | Notes |
|------|--------|--------|-------|
| FastAPI structure | Working | A | 10 routers, 17 services, lifespan events |
| Database/Cache | Working | A | PostgreSQL 16 + Redis 7, async SQLAlchemy |
| Auth system | **Fully wired** | A | JWT + token blacklisting + `is_active` check |
| Auth enforcement | **All routes protected** | A | `get_current_user_id` dependency on all routes |
| Transaction CRUD | Working | A | Soft-delete, duplicate detection, auto-categorization |
| Budget CRUD + tracking | Working | A- | Optimization suggestions, progress tracking |
| Goal CRUD + tracking | Working | A- | Division-by-zero fixed, risk alerts |
| Reports | Working | B+ | CSV export working, PDF via reportlab |
| File import/export | Working | B+ | CSV/XLSX import, template download |
| ML Categorization | Working | B- | TF-IDF + NB on synthetic data (~170 samples) |
| Prediction Engine | Functional but slow | C+ | ARIMA grid-searches 50+ params per call |
| AI Brain LLM | Requires NVIDIA GPU | C | Works via HTTP mode, 4 runtime bugs remain |
| RAG System | Mock data only | D | rag_retriever.py returns hardcoded data |
| Input/Output Guards | **Wired** | A- | SecurityMiddleware registered in main.py |
| Prometheus Metrics | Working | A- | 18 AI + 13 GPU metrics, 18 alert rules |
| Test Suite | 57/57 passing | A- | 28 files, 100% pass rate, needs more coverage |
| Frontend | 7 pages working | B- | React 19, only 2 reusable components |
| Security | Strong | B+ | JWT, blacklisting, guards, rate limiting |
| `datetime.utcnow()` | **22 occurrences remain** | C | Deprecated since Python 3.12, unfixed |

---

## Phase Structure

| Phase | Document | Focus | Estimated Effort | Progress |
|-------|----------|-------|-----------------|----------|
| **P0** | [01_P0_CRITICAL_SECURITY.md](01_P0_CRITICAL_SECURITY.md) | Auth enforcement, error leaking, critical bugs | 2-3 days | ~88% |
| **P1** | [02_P1_BACKEND_FIXES.md](02_P1_BACKEND_FIXES.md) | Middleware wiring, PDF, token blacklist, datetime, schema fixes | 3-4 days | ~85% |
| **P2** | [03_P2_ML_AI_FIXES.md](03_P2_ML_AI_FIXES.md) | Training data, ARIMA caching, RAG implementation, AI Brain fixes | 5-7 days | ~13% |
| **P3** | [04_P3_FRONTEND_COMPLETION.md](04_P3_FRONTEND_COMPLETION.md) | Components, design system, UX, accessibility | 5-7 days | ~0% |
| **P4** | [05_P4_TESTING_QUALITY.md](05_P4_TESTING_QUALITY.md) | Test infra, missing tests, E2E, CI/CD | 3-5 days | ~12% |
| **P5** | [06_P5_PRODUCTION_HARDENING.md](06_P5_PRODUCTION_HARDENING.md) | Rate limiting, encryption, monitoring, deployment, performance | 3-4 days | ~8% |

**Total estimated effort: 21-30 days**

---

## Dependency Graph

```
P0 (Security) ──────────────┐
                             ├──► P1 (Backend Fixes) ──► P5 (Production)
                             │
P2 (ML/AI) ─────────────────┤
                             │
P3 (Frontend) ──────────────┤
                             │
P4 (Testing) ───────────────┘
```

- **P0 must be done first** — everything depends on auth being enforced
- **P1 depends on P0** — middleware wiring needs the auth dependency to exist
- **P2, P3, P4 can run in parallel** after P0 is done
- **P5 (production hardening) is last** — needs all functional code to be stable

---

## Master Progress Tracker

### Phase 0 — Critical Security (MUST DO FIRST) — ~88% Done
- [x] Create `app/dependencies.py` with `get_current_user`
- [x] Create `app/dependencies.py` with `get_current_user_id`
- [x] Wire auth into `transactions.py` — `create_transaction`
- [x] Wire auth into `transactions.py` — `list_transactions`
- [x] Wire auth into `transactions.py` — `get_transaction`
- [x] Wire auth into `transactions.py` — `update_transaction`
- [x] Wire auth into `transactions.py` — `delete_transaction`
- [x] Wire auth into `budgets.py` — all 8 endpoints
- [x] Wire auth into `goals.py` — all 8 endpoints + fix route ordering
- [x] Wire auth into `predictions.py` — all 3 endpoints
- [x] Wire auth into `advice.py` — all 3 endpoints
- [x] Wire auth into `reports.py` — all 3 endpoints + remove user_id from body
- [x] Wire auth into `file_import.py` — all 2 endpoints
- [x] Wire auth into `ml.py` — all 6 auth-needed endpoints
- [x] Wire auth into `ai.py` — all 5 auth-needed endpoints
- [x] Refactor `auth.py` `/me` to use shared dependency
- [x] Replace `str(e)` with generic messages — `transactions.py` (5 handlers)
- [x] Replace `str(e)` with generic messages — `budgets.py` (8 handlers)
- [x] Replace `str(e)` with generic messages — `goals.py` (8 handlers)
- [x] Replace `str(e)` with generic messages — `predictions.py` (3 handlers)
- [x] Replace `str(e)` with generic messages — `advice.py` (3 handlers)
- [x] Replace `str(e)` with generic messages — `reports.py` (3 handlers)
- [x] Replace `str(e)` with generic messages — `file_import.py` (2 handlers)
- [x] Replace `str(e)` with generic messages — `ml.py` (6 handlers)
- [x] Replace `str(e)` with generic messages — `ai.py` (5 handlers)
- [x] Fix division-by-zero in `advice_generator.py` line 231
- [x] Fix category NULL mismatch — add fallback in `transaction_service.py`
- [x] Fix category NULL mismatch — update schema description
- [x] Add `is_active` field to `User` model
- [x] Add `is_active` check in auth dependency
- [x] Create Alembic migration for `is_active`
- [ ] Run ALL existing tests — verify no regressions
- [ ] Manual smoke test: register → login → CRUD with/without tokens

### Phase 1 — Backend Fixes — ~85% Done
- [x] Create `app/middleware/security.py` (SecurityMiddleware)
- [x] Register SecurityMiddleware in `main.py`
- [x] Add `blacklist_token` method to `AuthService`
- [x] Add `is_token_blacklisted` method to `AuthService`
- [x] Add blacklist check in `get_current_user` dependency
- [x] Update logout route to blacklist token
- [x] Blacklist old token on refresh
- [x] Fix PDF export — add `reportlab` to dependencies or return 501
- [ ] Replace `datetime.utcnow()` in all models (22 occurrences remain)
- [ ] Replace `datetime.utcnow()` in all services
- [ ] Replace `datetime.utcnow()` in all routes
- [x] Fix commit consistency — `auth_service.py` → flush
- [x] Fix commit consistency — `file_import_service.py` → flush
- [x] Ensure `get_db` commits on success
- [x] Remove dead `PASSWORD_PATTERN` in auth_service
- [x] Expand special char set in `validate_password`
- [x] Create `app/schemas/connection.py`
- [x] Create `app/schemas/ml_model.py`
- [x] Add `UserUpdate` schema to `auth.py`
- [x] Fix `created_at` type in `UserResponse`
- [x] Fix Decimal precision in budget allocations
- [x] Filter soft-deleted transactions from export
- [x] Fix merchant normalizer location regex for ALL-CAPS
- [x] Replace `hash()` with `hashlib.sha256` in ai_brain_service
- [x] Fix LRU cache memory leak in merchant_database
- [ ] Run ALL tests
- [ ] Manual smoke test all fixed flows

### Phase 2 — ML & AI Fixes — ~13% Done
- [ ] Create `app/constants/categories.py` — unified taxonomy
- [ ] Update `training_data.py` to import from constants
- [ ] Update `categorization_engine.py` to import from constants
- [ ] Update `ai_brain/inference/validation.py` to import from constants
- [ ] Update `rag_prompts.py` to import from constants
- [ ] Update `ai_validation.py` to import from constants
- [ ] Remove `preprocess_text()` from `training_data.py`
- [ ] Update `train_model.py` to use `preprocess_transaction`
- [ ] Create `data/training_transactions.json` with 1000+ entries
- [ ] Update `training_data.py` to load from JSON file
- [ ] Add data augmentation function
- [ ] Retrain ML model
- [ ] Cache ARIMA parameters per user+category
- [ ] Reduce ARIMA grid search space (50+ → 9)
- [ ] Add Redis caching for forecast results
- [ ] Fix MAPE accuracy metric for zero-values
- [ ] Fix AI Brain confidence API mismatch (TypeError)
- [ ] Fix `max_length` in brain_service.py
- [ ] Fix deprecated `asyncio.get_event_loop()`
- [ ] Fix `detect_mode` regex false positives
- [ ] Rewrite `rag_retriever.py` with real DB queries — spending summary
- [ ] Rewrite `rag_retriever.py` with real DB queries — recent transactions
- [ ] Rewrite `rag_retriever.py` with real DB queries — budgets
- [ ] Rewrite `rag_retriever.py` with real DB queries — goals
- [ ] Update `rag_context.py` to use database retriever
- [ ] Wire `templates.py` into `brain_service.py` response pipeline
- [ ] Wire ML service into AI validation singleton
- [ ] Fix case-sensitivity bug in `CATEGORY_TO_PARENT`
- [ ] Add deduplication to feedback collector
- [ ] Add category validation to feedback collector
- [ ] Run end-to-end test: transaction → categorization → AI → correction → retrain

### Phase 3 — Frontend Completion — ~0% Done
- [ ] Create `DataTable.tsx` component
- [ ] Create `FormField.tsx` component
- [ ] Create `Modal.tsx` component
- [ ] Create `Card.tsx` component
- [ ] Create `Button.tsx` component
- [ ] Create `Alert.tsx` component
- [ ] Create `LoadingSkeleton.tsx` component
- [ ] Create `EmptyState.tsx` component
- [ ] Create `Badge.tsx` component
- [ ] Create `ConfirmDialog.tsx` component
- [ ] Create `ErrorBoundary.tsx` — global
- [ ] Wrap individual pages with ErrorBoundary
- [ ] Create `ToastContext.tsx`
- [ ] Create `ToastContainer.tsx`
- [ ] Create `useForm.ts` hook
- [ ] Create `variables.css` design system
- [ ] Create `global.css`
- [ ] Import design system in `main.tsx`
- [ ] Refactor existing CSS to use variables
- [ ] Enhance DashboardPage with Card, LoadingSkeleton, period selector
- [ ] Enhance TransactionsPage with DataTable, Modal, search/filter
- [ ] Enhance BudgetsPage with Card, progress bars, optimization UI
- [ ] Enhance GoalsPage with Card, progress ring, risk badges
- [ ] Enhance ReportsPage with date picker, tabs, export buttons
- [ ] Enhance LoginPage with FormField, validation, show/hide password
- [ ] Enhance RegisterPage with FormField, password strength
- [ ] Create `useDebounce.ts` hook
- [ ] Create `useLocalStorage.ts` hook
- [ ] Create `usePagination.ts` hook
- [ ] Create `useMediaQuery.ts` hook
- [ ] Add ARIA labels to all interactive elements
- [ ] Add focus trapping to Modal
- [ ] Add keyboard navigation (Escape to close, skip nav link)
- [ ] Verify color contrast WCAG AA compliance
- [ ] Create `frontend/src/api/errors.ts` — ApiError class
- [ ] Update all API functions to use `handleApiError`
- [ ] Wire API errors to toast notifications
- [ ] Create Settings page (`/settings`)
- [ ] Create AI Chat page (`/ai-chat`)
- [ ] Create Import/Export page (`/import`)
- [ ] Visual review — light mode
- [ ] Visual review — dark mode
- [ ] Lighthouse accessibility audit ≥ 90

### Phase 4 — Testing & Quality — ~12% Done
- [ ] Add `aiosqlite` to test dependencies
- [ ] Update `conftest.py` for SQLite fallback
- [ ] Mark PostgreSQL-only tests with `@requires_postgres`
- [ ] Create `tests/test_input_guard.py` — safe input tests
- [ ] Create `tests/test_input_guard.py` — prompt injection tests
- [ ] Create `tests/test_input_guard.py` — code injection tests
- [ ] Create `tests/test_input_guard.py` — edge case tests
- [ ] Create `tests/test_output_guard.py` — safe content tests
- [ ] Create `tests/test_output_guard.py` — PII detection tests
- [ ] Create `tests/test_output_guard.py` — harmful advice tests
- [ ] Create `tests/test_output_guard.py` — hallucination tests
- [ ] Add `auth_headers` fixture to conftest
- [ ] Add unauthorized tests to `test_transaction_routes.py`
- [ ] Add unauthorized tests to `test_budget_routes.py`
- [ ] Add unauthorized tests to `test_goal_routes.py`
- [ ] Add unauthorized tests to `test_advice_routes.py`
- [ ] Add unauthorized tests to `test_report_routes.py`
- [ ] Add unauthorized tests to `test_prediction_routes.py`
- [ ] Add unauthorized tests to `test_file_import_routes.py`
- [ ] Rewrite `test_e2e_integration.py` — register/login flow
- [ ] Rewrite `test_e2e_integration.py` — CRUD flow
- [ ] Rewrite `test_e2e_integration.py` — import/export flow
- [ ] Create `frontend/playwright.config.ts`
- [ ] Create `frontend/tests/auth.spec.ts`
- [ ] Create `frontend/tests/transactions.spec.ts`
- [ ] Create `frontend/tests/dashboard.spec.ts`
- [ ] Create `.github/workflows/ci.yml` — backend tests job
- [ ] Create `.github/workflows/ci.yml` — frontend tests job
- [ ] Create `.github/workflows/ci.yml` — type-check job
- [x] Add `pytest-cov` to dependencies
- [x] Configure coverage in `pyproject.toml`
- [ ] Verify coverage ≥ 70%
- [ ] All tests pass locally
- [ ] CI pipeline runs green on a PR

### Phase 5 — Production Hardening — ~8% Done
- [ ] Create `app/middleware/rate_limiter.py`
- [ ] Define rate limit rules per endpoint group
- [ ] Register RateLimitMiddleware in `main.py`
- [ ] Fix encryption — use env-based salt
- [ ] Fix encryption — increase PBKDF2 to 600K iterations
- [ ] Fix encryption — lazy initialization
- [ ] Add file upload size limit (10MB)
- [ ] Add file content type validation
- [ ] Create `docker-compose.prod.yml` — API service
- [ ] Create `docker-compose.prod.yml` — frontend service
- [ ] Create `docker-compose.prod.yml` — PostgreSQL service
- [ ] Create `docker-compose.prod.yml` — Redis service
- [ ] Create `docker-compose.prod.yml` — Nginx service
- [ ] Create `docker-compose.prod.yml` — Prometheus + Grafana
- [ ] Create `frontend/Dockerfile`
- [ ] Create `nginx/nginx.conf` with security headers
- [x] Implement structured JSON logging (`JSONFormatter`)
- [ ] Update `logging_config.py` with `setup_logging()`
- [ ] Call `setup_logging()` in `main.py`
- [ ] Add `deleted_at` column to Budget model
- [ ] Add `deleted_at` column to Goal model
- [ ] Update budget service to soft-delete
- [ ] Update goal service to soft-delete
- [ ] Add `deleted_at` filter to all budget/goal read queries
- [ ] Create Alembic migration for soft-delete columns
- [ ] Create `app/middleware/request_id.py`
- [ ] Register RequestIDMiddleware in `main.py`
- [x] Create `.env.example`
- [ ] Add missing database indexes (Transaction.date, composite)
- [ ] Tune connection pool settings
- [ ] Set Redis `maxmemory-policy`
- [ ] Pre-load ML model at startup
- [ ] Add React.lazy() code splitting for pages
- [ ] Create `scripts/backup.sh`
- [ ] Add backup service to docker-compose.prod.yml
- [ ] Load test with 100 concurrent users
- [ ] Security audit (OWASP Top 10 checklist)
- [ ] Full deployment test on staging server

---

## Success Criteria (Definition of "Done")

- [x] **Zero auth bypass** — every endpoint validates JWT tokens
- [x] **Error redaction** — generic messages in production, real errors in logs
- [x] **Critical bug fixes** — division-by-zero, category NULL fallback, route ordering
- [ ] **datetime modernized** — replace all 22 `datetime.utcnow()` with `datetime.now(timezone.utc)`
- [ ] **Working AI Brain** — at minimum via HTTP mode with documented setup
- [ ] **Real RAG** — database-backed context retrieval, not mock data
- [ ] **Production ML** — real training data, cached predictions, consistent taxonomy
- [ ] **Complete frontend** — reusable components, error handling, loading states, form validation
- [ ] **Comprehensive tests** — 300+ tests, middleware coverage, working E2E, no live DB requirement
- [ ] **CI/CD pipeline** — automated testing, linting, building on every PR
- [ ] **Production-ready deployment** — Docker compose, nginx, SSL, rate limiting, monitoring
- [ ] **Security hardened** — rate limiting everywhere, proper encryption, token blacklisting, input validation
