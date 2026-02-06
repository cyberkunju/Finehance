# Financial AI Brain

**Base Model:** Qwen 2.5-3B-Instruct  
**Fine-Tuning:** QLoRA (4-bit NF4 quantization, LoRA rank 64, alpha 128)  
**Training Hardware:** NVIDIA Tesla P100 (16GB) on Kaggle  
**Inference Target:** RTX 4060 / RTX 3060 (8GB VRAM)

---

## Documentation Index

1. [**01_MODEL_ARCHITECTURE.md**](docs/01_MODEL_ARCHITECTURE.md)  
   Architectural decisions — why Qwen 2.5-3B, why QLoRA, the hybrid "Tag & Sum" approach.

2. [**02_DATASET_AND_TRAINING.md**](docs/02_DATASET_AND_TRAINING.md)  
   Training data (Sujet-Finance-Instruct-177k), ChatML formatting, hyperparameters, Kaggle infrastructure.

3. [**03_IMPLEMENTATION_GUIDE.md**](docs/03_IMPLEMENTATION_GUIDE.md)  
   How to integrate the model — strict mode prompt patterns, structured JSON output, Python post-processing.

4. [**04_PERFORMANCE_REPORT.md**](docs/04_PERFORMANCE_REPORT.md)  
   Raw vs fine-tuned comparison — categorization accuracy (~95%), tone shift, hallucination reduction.

---

## Architecture

The AI Brain runs as a standalone inference server (port 8080) accessed by the backend via HTTP.

```
Backend API (port 8000)
    │
    ├── app/services/ai_brain_service.py   ← HTTP client with circuit breaker
    │       │
    │       ▼
    AI Brain Server (port 8080)
        ├── inference/brain_service.py     ← Model loading, generation, mode routing
        ├── inference/confidence.py        ← Multi-factor confidence scoring
        ├── inference/rag_retriever.py     ← Context retrieval (currently mock data)
        ├── inference/templates.py         ← Response formatting (not yet wired)
        └── inference/validation.py        ← Category validation, hallucination detection
```

### Inference Modes

| Mode | Purpose | Output |
|------|---------|--------|
| **Chat** | General financial Q&A | Natural language response |
| **Analyze** | Spending pattern analysis | Structured analysis with insights |
| **Parse** | Transaction classification | JSON with category, amount, merchant |

---

## Directory Structure

```
ai_brain/
├── __init__.py
├── README.md                           ← You are here
├── requirements.txt                    # AI Brain Python dependencies
├── config/
│   ├── __init__.py
│   └── training_config.yaml            # QLoRA training hyperparameters
├── docs/
│   ├── 01_MODEL_ARCHITECTURE.md
│   ├── 02_DATASET_AND_TRAINING.md
│   ├── 03_IMPLEMENTATION_GUIDE.md
│   └── 04_PERFORMANCE_REPORT.md
├── inference/
│   ├── __init__.py
│   ├── brain_service.py                # Core inference service
│   ├── confidence.py                   # Confidence scoring engine
│   ├── rag_retriever.py                # RAG context retrieval
│   ├── templates.py                    # Response formatting templates
│   └── validation.py                   # Output validation and fact-checking
└── models/
    ├── financial-brain-final/          # Final LoRA adapter weights
    ├── financial-brain-qlora/          # QLoRA adapter weights (~456 MB)
    └── test_results.json               # Validation test results
```

---

## Running the AI Brain

### Via Docker (Recommended)

Requires an NVIDIA GPU with Docker GPU support configured:

```bash
# Start with GPU profile
docker-compose --profile gpu up -d ai-brain

# Check health
curl http://localhost:8080/health
```

### Training Configuration

Key settings from `config/training_config.yaml`:

| Parameter | Value |
|-----------|-------|
| Base model | `Qwen/Qwen2.5-3B-Instruct` |
| Quantization | 4-bit NF4 |
| Compute dtype | BF16 |
| LoRA rank | 64 |
| LoRA alpha | 128 |
| Target modules | All linear layers (q/k/v/o/gate/up/down_proj) |
| Sequence length | 2048 |
| Effective batch size | 16 (micro=2 × grad_accum=8) |
| Learning rate | 2e-4 (cosine scheduler) |
| Epochs | 3 |

---

## Integration with Backend

The backend communicates with the AI Brain via `app/services/ai_brain_service.py`:

- **Circuit breaker** — prevents cascading failures if AI Brain is down
- **Request queue** — semaphore limits concurrent requests (max 3)
- **Retry with backoff** — exponential backoff on transient failures
- **Timeout escalation** — configurable per-request timeouts
- **Fallback** — graceful degradation when AI Brain is unavailable

---

## Known Issues

1. **Confidence API mismatch** — `brain_service.py` passes `(float, str)` to `should_add_disclaimer()` but it expects a `ConfidenceResult` object → TypeError at runtime
2. **`max_length` too restrictive** — Set to `2048 - max_new_tokens` but Qwen supports 32K context
3. **Deprecated `asyncio.get_event_loop()`** — Should use `asyncio.get_running_loop()`
4. **`detect_mode` regex false positives** — `r"^[A-Z]{2,}"` matches any 2+ uppercase letters, not just transaction patterns
5. **RAG returns mock data** — `rag_retriever.py` returns hardcoded spending data instead of querying the database
6. **Templates not wired** — `templates.py` response formatter exists but is never called by `brain_service.py`

These are tracked in the [P2 roadmap](../roadmap/03_P2_ML_AI_FIXES.md).

---

## Design Philosophy

**"Let AI map the world. Let Code count the cost."**

The model is used strictly for semantic understanding and classification. All arithmetic is handled by Python. This "Tag & Sum" architecture avoids the LLM's weakness in calculation while leveraging its strength in language understanding.
