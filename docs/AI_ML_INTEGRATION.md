# AI/ML Integration Guide

> **Last Updated:** February 6, 2026  
> **Verified Against Codebase:** February 6, 2026

This document explains the AI and ML capabilities of the AI Finance Platform.

## Architecture Overview

The platform uses a **two-tier ML architecture** plus a **RAG pipeline** for accuracy improvement:

### Tier 1: Core ML (Always Active)
Located in `app/ml/`, these models are lightweight and run on CPU:

- **Transaction Categorization**: TF-IDF + Naive Bayes classifier
  - Global model trained on general transaction data
  - Per-user models that learn from corrections
  - ~0.85–0.95 accuracy depending on transaction clarity

- **Expense Prediction**: ARIMA/SARIMAX time series models
  - Forecasts future spending by category
  - Automatic anomaly detection
  - Model recalibration when accuracy drops

### Tier 2: AI Brain (Optional, GPU Required)
Located in `ai_brain/`, this is a fine-tuned Qwen 2.5-3B LLM:

- **Conversational Finance Assistant**: Natural language Q&A
- **Deep Financial Analysis**: Comprehensive spending insights
- **Smart Transaction Parsing**: Intelligent merchant/category extraction
- **Personalized Advice**: Context-aware financial recommendations

### RAG Pipeline (Integrated)
Located in `app/services/`, enhances AI Brain accuracy without retraining:

- **Merchant Database**: 285 merchants, 48 regex patterns, 4-stage lookup
- **RAG Context Builder**: Enriches prompts with grounded financial context
- **Merchant Normalizer**: Cleans raw transaction strings for matching
- **Feedback Collector**: User corrections → consensus → auto-update merchant DB

## API Endpoints

### ML Model Management (`/api/ml/`)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/status` | GET | No | Get overall ML system status |
| `/models/global` | GET | No | Get global model info |
| `/models/user/me` | GET | JWT | Get current user's model status |
| `/categorize` | POST | JWT | Categorize a single transaction |
| `/categorize/batch` | POST | JWT | Categorize multiple transactions |
| `/corrections` | POST | JWT | Submit a categorization correction |
| `/models/user/me/train` | POST | JWT | Manually trigger user model training |
| `/models/user/me` | DELETE | JWT | Delete user's personalized model |
| `/categories` | GET | No | Get available categories |

### AI Brain (`/api/ai/`)

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/status` | GET | No | 30/min | Get AI Brain service status |
| `/chat` | POST | JWT | 5/min, 100/hr | Chat with the AI assistant |
| `/analyze` | POST | JWT | 5/min, 100/hr | Request financial analysis |
| `/parse-transaction` | POST | JWT | 30/min | Parse transaction description |
| `/smart-advice` | POST | JWT | 5/min, 100/hr | Get personalized AI-powered advice |
| `/feedback/correction` | POST | JWT | 30/min | Submit a category correction |
| `/feedback/stats` | GET | JWT | 10/min | Get feedback statistics |

### Security Middleware (on AI endpoints)

All AI endpoints are protected by:
- **InputGuard** (448 lines) — 7 attack categories, 46 regex patterns, prompt injection detection
- **OutputGuard** (614 lines) — PII masking (8 types), harmful advice detection (11 patterns), hallucination flagging (5 patterns)
- **slowapi Rate Limiter** — per-user/IP rate limiting as shown above

## Usage Examples

### Categorize a Transaction

```bash
curl -X POST http://localhost:8000/api/ml/categorize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{"description": "STARBUCKS COFFEE #12345", "amount": 5.50}'
```

Response:
```json
{
  "category": "Food & Dining",
  "confidence": 0.999,
  "model_type": "GLOBAL",
  "llm_enhanced": false
}
```

### Batch Categorization

```bash
curl -X POST http://localhost:8000/api/ml/categorize/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "transactions": [
      {"description": "UBER TRIP", "amount": 15},
      {"description": "NETFLIX MONTHLY", "amount": 14.99}
    ]
  }'
```

### Submit ML Correction (Improves Personalization)

```bash
curl -X POST http://localhost:8000/api/ml/corrections \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "description": "DOORDASH*THAI FOOD",
    "correct_category": "Food & Dining"
  }'
```

### Chat with AI

```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "message": "How can I reduce my food spending?",
    "context": {
      "monthly_income": 5000,
      "spending": {"Food & Dining": 800, "Shopping": 400}
    }
  }'
```

### Get Smart Advice

```bash
curl -X POST http://localhost:8000/api/ai/smart-advice \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "include_transactions": true,
    "include_goals": true,
    "max_recommendations": 5
  }'
```

### Submit AI Category Correction (Feeds RAG Loop)

```bash
curl -X POST http://localhost:8000/api/ai/feedback/correction \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "merchant_raw": "WHOLEFDS 12345 AUSTIN TX",
    "original_category": "Fast Food",
    "corrected_category": "Groceries"
  }'
```

### Get Feedback Stats

```bash
curl http://localhost:8000/api/ai/feedback/stats \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

## Running with GPU (AI Brain)

To enable the AI Brain LLM service, you need an NVIDIA GPU with CUDA support.

### Prerequisites
- NVIDIA GPU with 6GB+ VRAM (tested on RTX 4060 8GB)
- NVIDIA Container Toolkit installed
- CUDA drivers installed (591.x+ recommended)
- Docker Desktop with WSL2 (Windows) or Docker CE (Linux)

### Verify GPU Access

```bash
# Check GPU is detected
nvidia-smi

# Verify Docker can access GPU
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### Build AI Brain Image

```bash
# Build the GPU-enabled container (first time takes 10-15 minutes)
docker compose build ai-brain
```

### Start with GPU Support

```bash
# Start all services including AI Brain
docker compose --profile gpu up -d

# Or start just AI Brain
docker compose --profile gpu up -d ai-brain

# View AI Brain logs (model loading takes 1-2 minutes)
docker logs -f ai-finance-ai-brain
```

### Verify AI Brain is Running

```bash
# Direct health check
curl http://localhost:8080/health

# Check status through main app
curl http://localhost:8000/api/ai/status
# Should show: {"enabled": true, "available": true, "model_loaded": true}
```

### Model Location

The trained model should be in `ai_brain/models/financial-brain-qlora/`:
```
ai_brain/models/
├── financial-brain-qlora/
│   ├── adapter_config.json      # LoRA adapter configuration
│   ├── adapter_model.safetensors # Fine-tuned weights (~456 MB)
│   ├── tokenizer.json
│   ├── tokenizer_config.json
│   └── special_tokens_map.json
```

The base model (Qwen/Qwen2.5-3B-Instruct, ~6GB) is downloaded automatically on first run.

### Troubleshooting GPU Issues

```bash
# Check if NVIDIA driver is loaded
nvidia-smi

# Check Docker NVIDIA runtime
docker info | grep -i nvidia

# Test GPU memory allocation
docker run --rm --gpus all nvidia/cuda:12.2.0-devel-ubuntu22.04 \
  python3 -c "import torch; print(torch.cuda.is_available())"

# View container GPU usage
nvidia-smi pmon -i 0 -s u -d 1
```

## Resilience & Fallback Behavior

The AI Brain service (`app/services/ai_brain_service.py`, 1135 lines) has a full resilience stack:

### Resilience Components

| Component | Implementation | Purpose |
|-----------|----------------|---------|
| **Circuit Breaker** | `CircuitBreaker` class | CLOSED→OPEN (3 failures)→HALF_OPEN (30s), prevents cascading failures |
| **Request Queue** | `RequestQueue` class | `asyncio.Semaphore(3)`, limits concurrent GPU requests |
| **Retry** | `_query_http_with_retry()` | Max 2 retries, exponential backoff 0.5→1→2s, no retry on 4xx |
| **Timeout Strategy** | `TimeoutStrategy` class | health=5s, parse=15s, chat=30s, analyze=60s, cold_start=90s |

### Fallback Chain

When the AI Brain is unavailable (circuit open, timeout, or error), the system automatically falls back to:

1. **Transaction Parsing**: Merchant database lookup (285 merchants) + regex matching (48 patterns) + ML categorization
2. **Chat**: Rule-based financial guidance from templates
3. **Analysis**: Basic statistical summary from transaction data

The fallback is transparent — responses include `"fallback": true` and lower confidence scores.

## RAG Pipeline Details

### How RAG Improves AI Accuracy

```
WITHOUT RAG:
  User: "Categorize: WHOLEFDS 12345 AUSTIN TX $89.52"
  AI Brain: 🤔 "WHOLEFDS... sounds like food... Fast Food?"
  Result: ❌ Wrong

WITH RAG:
  User: "Categorize: WHOLEFDS 12345 AUSTIN TX $89.52"
  RAG Pipeline:
    1. MerchantNormalizer → "wholefds"
    2. MerchantDatabase.lookup() → "Whole Foods Market" (Groceries)
    3. RAGContextBuilder → enriched prompt with merchant hint
  AI Brain: ✅ "Groceries" (high confidence)
```

### RAG Components (All Implemented)

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Merchant Database | `app/services/merchant_database.py` | 312 | 4-stage lookup: exact alias → regex → partial → fuzzy |
| Merchant Normalizer | `app/services/merchant_normalizer.py` | 259 | Clean raw transaction strings |
| RAG Context Builder | `app/services/rag_context.py` | 430 | Build enriched prompts for parse/chat/analyze |
| RAG Prompts | `app/services/rag_prompts.py` | 241 | Structured prompt templates |
| Feedback Collector | `app/services/feedback_collector.py` | 480 | Corrections → consensus → auto-update DB |
| Merchant Data | `data/merchants.json` | 2150 | 285 merchants, 48 regex patterns, 23 categories |

### Feedback Loop

1. User submits correction via `POST /api/ai/feedback/correction`
2. `FeedbackCollector` stores correction and checks consensus
3. When 3+ users correct the same merchant → same category, auto-updates `MerchantDatabase` at runtime
4. All corrections exportable as ChatML training data for future fine-tuning

## Quality Assurance

### AI Brain Validation Pipeline

All AI responses pass through:

1. **ConfidenceCalculator** (`ai_brain/inference/confidence.py`, 310 lines) — real confidence from token log probabilities
2. **ResponseValidator** (`ai_brain/inference/validation.py`, 693 lines):
   - `HallucinationDetector` — 7 patterns for fabricated data
   - `FinancialFactChecker` — blocks dangerous financial advice
   - `CategoryValidator` — 60+ merchant→category corrections
3. **AIMLCrossValidator** (`app/services/ai_validation.py`, 416 lines) — cross-validates AI categories against ML model predictions

### AI–ML Cross-Validation

When both tiers produce a category:
- If AI and ML agree → high confidence
- If they disagree → uses confidence-based override (threshold 0.85)
- Category hierarchy matching prevents false conflicts (e.g., "Fast Food" is a child of "Food & Dining")

## Configuration

Environment variables for ML/AI:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_STORAGE_PATH` | `./models` | Directory for ML models |
| `AI_BRAIN_ENABLED` | `true` | Enable AI Brain integration |
| `AI_BRAIN_MODE` | `http` | `http` (separate server) or `direct` (in-process) |
| `AI_BRAIN_URL` | `http://ai-brain:8080` | AI Brain server URL |
| `AI_BRAIN_MODEL_PATH` | `./ai_brain/models/financial-brain-qlora` | Model path for direct mode |
| `AI_RATE_LIMIT_PER_MINUTE` | `5` | Rate limit for AI chat/analyze/advice |
| `AI_RATE_LIMIT_PER_HOUR` | `100` | Hourly rate limit for AI endpoints |
| `AI_RATE_LIMIT_PARSE` | `30` | Rate limit for parse-transaction |
| `ENABLE_METRICS` | `true` | Enable Prometheus metrics |
| `ENABLE_GPU_METRICS` | `true` | Enable GPU monitoring |
| `SENTRY_DSN` | (empty) | Sentry error tracking DSN |

## Performance Characteristics

### Tier 1 (Core ML)
- Latency: <10ms per categorization
- Memory: ~50MB for loaded models
- CPU-only, scales horizontally

### Tier 2 (AI Brain)
- Latency: 5–9s P50, 25–45s P99 (GPU-bound)
- Memory: ~6.4 GB VRAM (80% of RTX 4060)
- GPU required for acceptable performance
- Single instance recommended (model in GPU memory)
- Max 3 concurrent requests (RequestQueue enforced)

### RAG Pipeline
- Merchant lookup: <1ms (in-memory, cached)
- Context building: <5ms
- No GPU required (runs on app server CPU)

## Monitoring

### Prometheus Metrics (31 total)

| Category | Count | Examples |
|----------|-------|---------|
| AI Brain | 18 | request_duration, requests_total, circuit_state, confidence_score, queue_depth |
| GPU | 13 | memory_used, utilization, temperature, power_usage, model_loaded |

### Alert Rules (18 total, 5 groups)

| Group | Rules |
|-------|-------|
| AI Brain | High Error Rate, Circuit Open, Queue Backlog, Slow Responses, Queue Timeouts |
| GPU | Memory High/Critical, Temperature High/Critical, Utilization Sustained, Unavailable |
| Application | HTTP Error Rate, Slow Responses, High Concurrency |
| Security | Input Block Rate, Prompt Injection Attempts, PII Masking Rate |
| Rate Limits | Rate Limit Hits |

### Monitoring Endpoints

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# GPU metrics
curl http://localhost:8000/metrics/gpu

# AI Brain resilience stats
curl http://localhost:8000/metrics/ai

# Cache stats
curl http://localhost:8000/metrics/cache

# ML status
curl http://localhost:8000/api/ml/status

# AI Brain health
curl http://localhost:8000/api/ai/status

# Grafana dashboard
open http://localhost:3001  # 19 panels across 5 sections
```

## Training Your Own Models

### Global Categorization Model

```bash
# Generate training data
python app/ml/training_data.py

# Train the model
python app/ml/train_model.py
```

### AI Brain LLM

```bash
cd ai_brain

# Generate training data
python run.py generate

# Train with QLoRA (requires GPU)
python run.py train

# Test the model
python run.py cli
```

---

*Verified against codebase on February 6, 2026. All endpoints, line counts, and feature details confirmed by reading source files directly.*
