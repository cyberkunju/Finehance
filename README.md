# Finehance — AI Finance Platform

An enterprise-grade personal finance management system featuring hybrid AI architecture for transaction intelligence, forecasting, and financial advice.

---

## System Architecture

The platform runs as a containerized microservice stack orchestrated via Docker Compose (7 services):

| Service | Technology | Port | Description |
| :--- | :--- | :--- | :--- |
| **Backend API (dev)** | Python 3.11, FastAPI | 8000 | Core REST API — business logic, auth, ML, data orchestration |
| **Backend API (prod)** | Python 3.11, FastAPI | 8001 | Production container (non-root `appuser`) |
| **AI Brain** | PyTorch, Qwen 2.5-3B | 8080 | Dedicated LLM inference server (GPU profile, requires NVIDIA GPU) |
| **Database** | PostgreSQL 16 Alpine | 5432 | Relational storage — users, transactions, budgets, goals, ML models |
| **Cache** | Redis 7 Alpine | 6379 | Session management, rate limiting, token blacklist, forecast cache |
| **Prometheus** | v2.49.1 | 9090 | Metrics scraping and alerting (monitoring profile) |
| **Grafana** | v10.3.1 | 3001 | Dashboards for system health and AI metrics (monitoring profile) |

---

## Key Features

### Transaction Management
- Full CRUD with soft-delete support
- AI-powered auto-categorization (leave category blank → ML assigns it)
- Duplicate detection, advanced filtering and search
- Bulk import from CSV/XLSX, export to CSV
- Template download for structured imports

### Hybrid AI Categorization
Two-tier approach for speed and accuracy:
- **Tier 1 (Fast)**: TF-IDF + Multinomial Naive Bayes — millisecond-latency categorization of known merchants
- **Tier 2 (Smart)**: Qwen 2.5-3B LLM with QLoRA adapter — handles ambiguous or novel transactions
- **Feedback Loop**: User corrections feed back to improve categorization over time

### Financial AI Assistant (RAG)
Context-aware LLM assistant powered by Retrieval-Augmented Generation:
- Merchant database (285 merchants, 48 regex patterns)
- RAG context builder injects spending summaries, budgets, and goals before answering
- Confidence scoring with hallucination detection and financial fact-checking

### Financial Planning
- **Budgets**: Period-based budgets with category allocations, real-time progress tracking, AI-powered optimization suggestions
- **Goals**: Financial targets with automatic progress tracking, risk alerts, deadline projections
- **Forecasting**: ARIMA time-series predictions for 30/60/90 day expense forecasts
- **Advice**: Personalized recommendations based on spending patterns

### Reports & Analytics
- Custom date-range financial reports
- Income vs expense breakdowns, savings rate calculation
- Budget adherence analysis
- Export to CSV and PDF (via ReportLab)

### Security
- JWT authentication (HS256) with token blacklisting via Redis
- Password strength enforcement (12+ characters, mixed case, numbers, special chars)
- InputGuard (448 lines, 46 patterns, 7 attack categories) + OutputGuard (614 lines, PII masking)
- SecurityMiddleware registered in ASGI pipeline
- Non-root Docker users, CORS hardening, rate limiting (slowapi)

---

## Quick Start

### Prerequisites
- Docker Engine & Docker Compose

### 1. Start the Stack

```bash
# Start core services (postgres, redis, dev, app)
docker-compose up -d --build

# Also start monitoring (optional)
docker-compose --profile monitoring up -d

# Also start AI Brain (requires NVIDIA GPU)
docker-compose --profile gpu up -d
```

### 2. Run Database Migrations

```bash
docker-compose exec dev alembic upgrade head
```

### 3. Access the Application

| Service | URL |
|---------|-----|
| Backend API (dev) | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Backend API (prod) | http://localhost:8001 |
| AI Brain | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |

### 4. Frontend Development

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# Available at http://localhost:5173
```

### Environment Configuration

Create a `.env` file from the template:
```bash
cp .env.example .env
```

See `.env.example` for all configuration options including database, Redis, JWT, rate limiting, ML, AI Brain, and monitoring settings.

---

## Project Structure

```
├── app/                        # Core Backend API (FastAPI)
│   ├── models/                 # SQLAlchemy ORM models (7 files)
│   ├── schemas/                # Pydantic validation schemas (10 files)
│   ├── services/               # Business logic layer (17 services)
│   ├── routes/                 # API route handlers (10 routers)
│   ├── ml/                     # ML pipeline (5 modules)
│   ├── middleware/              # InputGuard, OutputGuard, SecurityMiddleware
│   ├── metrics/                # Prometheus + GPU metrics collection
│   ├── config.py               # Pydantic settings (env-based)
│   ├── database.py             # Async SQLAlchemy setup
│   ├── cache.py                # Redis cache manager
│   ├── dependencies.py         # Shared auth dependencies
│   ├── logging_config.py       # Structured logging config
│   └── main.py                 # FastAPI app (middleware, routers, health checks)
├── ai_brain/                   # LLM Inference Service
│   ├── inference/              # brain_service, confidence, rag_retriever, templates, validation
│   ├── models/                 # LoRA adapter weights (~456 MB)
│   ├── config/                 # training_config.yaml
│   └── docs/                   # Model architecture, training, implementation docs
├── frontend/                   # React 19 + TypeScript + Vite
│   └── src/
│       ├── api/                # 8 API client modules
│       ├── components/         # Layout, ThemeToggle
│       ├── contexts/           # AuthContext, ThemeContext
│       ├── pages/              # 7 pages (Dashboard, Transactions, Budgets, Goals, Reports, Login, Register)
│       └── types/              # TypeScript definitions
├── tests/                      # Pytest suite (28 files, 57 tests, 100% pass rate)
├── alembic/                    # Database migrations
├── data/                       # merchants.json (285 merchants), feedback storage
├── docs/                       # Full documentation suite
├── roadmap/                    # Production perfection roadmap (P0–P5)
├── grafana/                    # Dashboard JSON + provisioning
├── prometheus/                 # Scrape config + 18 alert rules
├── models/                     # Trained ML model artifacts
├── scripts/                    # Utility scripts
├── docker-compose.yml          # 7 services orchestration
├── Dockerfile                  # Production backend (non-root appuser)
├── Dockerfile.dev              # Development backend
├── Dockerfile.ai-brain         # AI Brain GPU container (non-root aiuser)
├── .env.example                # Environment variable template
└── pyproject.toml              # Python dependencies (Poetry)
```

---

## AI Capabilities

### Fast Path — Local ML (`app/ml/`)
- **Engine**: Scikit-learn (TF-IDF vectorizer + Multinomial Naive Bayes)
- **Speed**: Sub-millisecond inference
- **Use case**: Categorizing known merchant transactions (e.g., "STARBUCKS" → Dining)

### Smart Path — AI Brain (`ai_brain/`)
- **Model**: Qwen 2.5-3B-Instruct with QLoRA adapter (4-bit NF4 quantization)
- **VRAM**: Optimized for 8GB (RTX 4060 / RTX 3060)
- **Training**: Fine-tuned on Sujet-Finance-Instruct-177k dataset via Kaggle P100
- **Capabilities**: Transaction parsing, financial advice, anomaly detection, complex reasoning
- **Architecture**: "Tag & Sum" — LLM classifies, Python calculates (avoids math hallucinations)

### RAG Pipeline
- **Merchant Database**: 285 merchants with 48 regex patterns for normalization
- **Context Builder**: Injects user's spending summary, recent transactions, budgets, goals
- **Feedback Collector**: Records user corrections for continuous improvement
- **Confidence System**: Multi-factor scoring with disclaimer generation

---

## Testing

```bash
# Run all backend tests (inside dev container)
docker-compose exec dev poetry run pytest tests/ -v

# From host via Make
make dev-test

# Frontend tests (Playwright configured)
cd frontend && npx playwright test
```

**Current status**: 28 test files, 57/57 passing (100% pass rate)

---

## Monitoring

When the monitoring profile is active:
- **Prometheus** scrapes the backend (10s interval) and AI Brain (30s interval)
- **18 alert rules** defined in `prometheus/alerts.yml`
- **Grafana** dashboard for AI Brain metrics at http://localhost:3001
- **Sentry** integration available (configure `SENTRY_DSN` in `.env`)

---

## Documentation

Full documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | End-user walkthrough |
| [API Documentation](docs/API_DOCUMENTATION.md) | REST API reference (all endpoints) |
| [Code Documentation](docs/CODE_DOCUMENTATION.md) | Codebase architecture guide |
| [Database Schema](docs/DATABASE_SCHEMA.md) | Table definitions and relationships |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [Docker Development](docs/DOCKER_DEVELOPMENT.md) | Local dev environment setup |
| [Release Notes](docs/RELEASE_NOTES.md) | Version history |
| [AI/ML Integration](docs/AI_ML_INTEGRATION.md) | Two-tier ML + LLM architecture |
| [AI Brain Production Roadmap](docs/AI_BRAIN_PRODUCTION_ROADMAP.md) | AI Brain readiness assessment (Phases 1–5) |
| [Production Roadmap](roadmap/00_ROADMAP_OVERVIEW.md) | Full P0–P5 improvement tracker |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| **Database** | PostgreSQL 16, Alembic migrations |
| **Cache** | Redis 7 |
| **ML** | scikit-learn, statsmodels (ARIMA), pandas, numpy |
| **LLM** | Qwen 2.5-3B-Instruct, PyTorch, PEFT (QLoRA), bitsandbytes |
| **Frontend** | React 19.2, TypeScript 5.9, Vite (rolldown), React Router 7, TanStack Query 5, Chart.js 4, Lucide React |
| **Infrastructure** | Docker Compose, Prometheus, Grafana, Sentry |
| **Security** | python-jose (JWT), passlib (bcrypt), slowapi, InputGuard/OutputGuard |
| **Testing** | pytest, pytest-asyncio, pytest-cov, httpx, hypothesis, Playwright |

---

## License

Proprietary / Private

**Repository**: [github.com/cyberkunju/Finehance](https://github.com/cyberkunju/Finehance)

