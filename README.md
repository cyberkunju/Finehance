# AI Finance Platform

An enterprise-grade personal finance management system featuring hybrid AI architecture for transaction intelligence, forecasting, and financial advice. Use this platform to track finances, receive automated insights, and manage budgets with high precision.

---

## 🏗️ System Architecture

The platform operates on a microservice-like architecture composed of five primary containers:

| Service | Technology | Description |
| :--- | :--- | :--- |
| **Backend API** | Python 3.11, FastAPI | The core REST API handling business logic, authentication, and data orchestration. |
| **AI Brain** | Python, PyTorch, Qwen-2.5 | Dedicated inference server for the LLM-based financial assistant (RAG). |
| **Frontend** | React 19, Vite, TypeScript | Modern responsive web interface for users. |
| **Database** | PostgreSQL 16 | Relational storage for users, transactions, and vector embeddings. |
| **Cache** | Redis 7 | High-speed cache for session management and rate limiting. |

**Observability Stack:**
- **Prometheus**: Metrics scraping and alerting.
- **Grafana**: Real-time dashboards for system health and model performance.

---

## 🚀 Key Features

### 1. Unified Transaction Management
- **Universal Import**: Supports file imports (likely CSV/OFX) and manual entry.
- **Smart Parsing**: Automatically detects merchants, dates, and amounts from raw description strings.

### 2. Hybrid AI Categorization Engine
A dual-layer approach to categorization for speed and accuracy:
- **Layer 1 (Fast)**: Scikit-learn `MultinomialNB` model for millisecond-latency categorization of known merchants.
- **Layer 2 (Smart)**: LLM-based analysis for ambiguous or novel transactions.
- **Feedback Loop**: User corrections retrain the local models to improve accuracy over time.

### 3. Financial AI Assistant (RAG)
Integrated "Brain" service that provides context-aware financial advice.
- **Context Injection**: Dynamically retrieves your recent spending, budget status, and goals before answering.
- **Capabilities**: Can answer questions like *"Can I afford a vacation?"* or *"Analyze my grocery spending trend."*

### 4. Advanced Financial Planning
- **Budgeting**: Set period-based budgets with real-time tracking.
- **Goal Tracking**: Define financial targets (e.g., "Emergency Fund") and track progress automatically.
- **Forecasting**: Predictive engine estimates future account balances based on recurring patterns.

---

## 🛠️ Installation & Setup

### Prerequisites
- Docker Engine & Docker Compose (Recommended)
- **OR** Python 3.11+, Node.js 18+, PostgreSQL, Redis (for manual setup)

### 1. Docker Setup (Production-Ready)
The platform is designed to run seamlessly in Docker.

```bash
# 1. Start the entire stack
docker-compose up -d --build

# 2. Run database migrations
docker-compose exec app alembic upgrade head

# 3. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# AI Brain: http://localhost:8080
```

### 2. Environment Configuration
Create a `.env` file in the root directory. See `.env.example` for all available options.

**Critical Variables:**
```ini
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db_name
SECRET_KEY=your_production_secret_key
ENCRYPTION_KEY=your_fernet_key
AI_BRAIN_URL=http://ai-brain:8080
```

### 3. Management Scripts
Reliable utility scripts are provided in the `/scripts` directory:

```bash
# Verify the deployment is healthy
python scripts/verify_deployment.py

# Manage the AI Brain (legacy)
python scripts/manage_brain.py
```

---

## 📂 Project Structure

```plaintext
root/
├── ai_brain/             # LLM Inference Service (Qwen model logic)
├── alembic/              # Database schema migrations
├── app/                  # Core Backend API (FastAPI)
│   ├── ml/               # Scikit-learn categorization engine
│   ├── services/         # Business logic (Auth, Transactions, RAG)
│   └── routes/           # API Endpoints
├── frontend/             # React/TypeScript Web Application
├── models/               # Binary model artifacts (Pickle/Safetensors)
├── grafana/              # Dashboards for monitoring
├── prometheus/           # Metrics configuration
├── tests/                # Pytest integration & unit tests
└── docker-compose.yml    # Container orchestration
```

---

## 🤖 AI Capabilities

The platform uses two distinct AI systems:

1.  **Fast Path (Local ML)**:
    *   **Located in**: `app/ml/`
    *   **Tech**: Scikit-Learn (TF-IDF + Naive Bayes)
    *   **Use Case**: Categorizing "Starbucks" -> "Food & Drink" instantly.

2.  **Smart Path (AI Brain)**:
    *   **Located in**: `ai_brain/` & `app/services/ai_brain_service.py`
    *   **Tech**: Qwen-2.5-3B (Quantized) + RAG
    *   **Use Case**: Complex reasoning, financial advice, and anomaly detection.

---

## 🧪 Testing

The project maintains a high standard of code quality with comprehensive tests.

```bash
# Run backend tests
docker-compose exec app pytest

# Run frontend tests
cd frontend && npm test
```

---

## 📄 Documentation

For developers extending the platform:
- **API Docs**: Available at `/docs` (Swagger UI) when the backend is running.
- **Database Schema**: See `alembic/versions` for the full history of schema changes.

**License**: Proprietary / Private

