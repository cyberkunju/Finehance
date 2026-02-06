# Release Notes — Version 1.0.0

**Release Date**: January 30, 2026  
**Repository**: [github.com/cyberkunju/Finehance](https://github.com/cyberkunju/Finehance)

---

## Overview

Initial release of Finehance — an AI-powered personal finance management platform combining traditional ML with LLM-based financial intelligence.

---

## Core Features

### Transaction Management
- Full CRUD with soft-delete support
- AI-powered auto-categorization (TF-IDF + Naive Bayes)
- Duplicate detection based on amount, date, and description
- Advanced filtering by category, type, date range, and search
- Bulk import from CSV and XLSX files with template download
- Export transactions to CSV

### Budget Management
- Period-based budgets with per-category allocations (JSONB storage)
- Real-time progress tracking with color-coded status indicators
- AI-powered budget optimization suggestions
- Budget vs actual spending analysis

### Financial Goals
- Target-based goals with deadline tracking
- Automatic progress calculation
- Risk alerts when progress falls behind schedule
- Status management (Active, Achieved, Archived)

### AI-Powered Features
- **Auto-Categorization**: TF-IDF + Multinomial Naive Bayes for instant categorization
- **Expense Predictions**: ARIMA time-series forecasting (30/60/90 days)
- **Personalized Advice**: Context-aware financial recommendations
- **Budget Optimization**: Smart reallocation suggestions based on spending patterns

### Reports & Analytics
- Custom date-range financial reports
- Income/expense breakdowns and savings rate calculation
- Budget adherence analysis
- Export to CSV and PDF (via ReportLab)

### Security
- JWT authentication (HS256) with token blacklisting via Redis
- Password strength enforcement (12+ chars, mixed case, numbers, special chars)
- InputGuard (448 lines, 46 patterns, 7 attack categories)
- OutputGuard (614 lines, PII masking, harmful advice blocking)
- SecurityMiddleware registered in ASGI pipeline
- Non-root Docker containers, CORS hardening, rate limiting (slowapi)

---

## Technical Stack

### Backend
- **Framework**: FastAPI (Python 3.11) with async SQLAlchemy 2.0
- **Database**: PostgreSQL 16 with Alembic migrations
- **Cache**: Redis 7 for sessions, rate limiting, token blacklist
- **ML**: scikit-learn (categorization), statsmodels (ARIMA predictions)
- **Architecture**: 10 routers, 17 services, 7 models, 10 schemas
- **Testing**: 28 test files, 57/57 passing (100% pass rate)

### Frontend
- **Framework**: React 19.2 with TypeScript 5.9
- **Build**: Vite (rolldown-vite)
- **State**: TanStack Query 5, AuthContext, ThemeContext
- **Charts**: Chart.js 4 (react-chartjs-2)
- **Routing**: React Router 7 with protected routes
- **Pages**: Dashboard, Transactions, Budgets, Goals, Reports, Login, Register

### AI Brain (GPU-Accelerated LLM)
- **Model**: Qwen 2.5-3B-Instruct with QLoRA adapter (~456 MB)
- **Inference**: 4-bit NF4 quantization, optimized for 8GB VRAM (RTX 4060)
- **Training**: Fine-tuned on Sujet-Finance-Instruct-177k via Kaggle P100
- **RAG**: 285-merchant database, context builder, feedback collector
- **Quality**: Confidence scoring, hallucination detection, financial fact-checking
- **Resilience**: Circuit breaker, request queue, retry with backoff, timeout escalation

### Infrastructure
- **Docker Compose**: 7 services (postgres, redis, dev, app, ai-brain, prometheus, grafana)
- **Monitoring**: Prometheus (18 AI + 13 GPU metrics), Grafana dashboards, Sentry
- **Alerting**: 18 Prometheus alert rules
- **Security**: Non-root users, slowapi rate limiting, CORS, env-based secrets

---

## Installation

### Docker (Recommended)

```bash
# Start core services
docker-compose up -d --build

# Run database migrations
docker-compose exec dev alembic upgrade head

# Start monitoring (optional)
docker-compose --profile monitoring up -d

# Start AI Brain (optional, requires NVIDIA GPU)
docker-compose --profile gpu up -d
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# Available at http://localhost:5173
```

See [Deployment Guide](DEPLOYMENT_GUIDE.md) for production setup.

---

## Known Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| `datetime.utcnow()` deprecated | Medium | 22 occurrences remain across models and services (Python 3.12+) |
| ARIMA predictions slow | Medium | Grid-searches 50+ parameter combinations per API call |
| RAG returns mock data | Medium | `rag_retriever.py` uses hardcoded data instead of DB queries |
| AI Brain runtime bugs | Medium | 4 issues in brain_service.py (confidence TypeError, max_length, asyncio, regex) |
| No CI/CD pipeline | Low | Tests run locally only |
| Frontend lacks component library | Low | All UI inline in page components |

---

## System Requirements

### Minimum
- CPU: 2 cores
- RAM: 4 GB
- Storage: 20 GB
- Docker Engine & Docker Compose

### Recommended
- CPU: 4+ cores
- RAM: 8+ GB
- Storage: 50+ GB SSD
- NVIDIA GPU with 8GB+ VRAM (for AI Brain)

---

## Roadmap

Active development is tracked in the `roadmap/` directory:

| Phase | Focus | Status |
|-------|-------|--------|
| P0 — Critical Security | Auth enforcement, error redaction, critical bugs | ~88% done |
| P1 — Backend Fixes | Middleware, token blacklist, datetime, schemas | ~85% done |
| P2 — ML/AI Fixes | Training data, ARIMA caching, RAG, AI Brain bugs | ~13% done |
| P3 — Frontend | Component library, design system, accessibility | ~0% done |
| P4 — Testing | Test infra, coverage, E2E, CI/CD | ~12% done |
| P5 — Production | Rate limiting, encryption, Docker prod, nginx | ~8% done |

See [roadmap/00_ROADMAP_OVERVIEW.md](../roadmap/00_ROADMAP_OVERVIEW.md) for the full tracker.

---

## Support

- **Issues**: [github.com/cyberkunju/Finehance/issues](https://github.com/cyberkunju/Finehance/issues)
- **API Docs**: `http://localhost:8000/docs` (Swagger UI, when backend is running)

---

**Version**: 1.0.0  
**Build**: Production
