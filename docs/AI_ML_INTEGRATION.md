# AI/ML Integration Guide

This document explains the AI and ML capabilities of the AI Finance Platform.

## Architecture Overview

The platform uses a **two-tier ML architecture**:

### Tier 1: Core ML (Always Active)
Located in `app/ml/`, these models are lightweight and run on CPU:

- **Transaction Categorization**: TF-IDF + Naive Bayes classifier
  - Global model trained on general transaction data
  - Per-user models that learn from corrections
  - ~0.85-0.95 accuracy depending on transaction clarity

- **Expense Prediction**: ARIMA/SARIMAX time series models
  - Forecasts future spending by category
  - Automatic anomaly detection
  - Model recalibration when accuracy drops

### Tier 2: AI Brain (Optional, GPU Required)
Located in `ai_brain/`, this is a fine-tuned Qwen 2.5-3B LLM:

- **Conversational Finance Assistant**: Natural language Q&A
- **Deep Financial Analysis**: Comprehensive spending insights
- **Smart Transaction Parsing**: Intelligent merchant/category extraction

## API Endpoints

### ML Model Management (`/api/ml/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Get overall ML system status |
| `/models/global` | GET | Get global model info |
| `/models/user/{user_id}` | GET | Get user model status |
| `/categorize` | POST | Categorize a single transaction |
| `/categorize/batch` | POST | Categorize multiple transactions |
| `/corrections` | POST | Submit a categorization correction |
| `/models/user/{user_id}/train` | POST | Manually trigger user model training |
| `/categories` | GET | Get available categories |

### AI Brain (`/api/ai/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Get AI Brain service status |
| `/chat` | POST | Chat with the AI assistant |
| `/analyze` | POST | Request financial analysis |
| `/parse-transaction` | POST | Parse transaction description |
| `/smart-advice` | POST | Get personalized AI-powered advice |

## Usage Examples

### Categorize a Transaction

```bash
curl -X POST http://localhost:8000/api/ml/categorize \
  -H "Content-Type: application/json" \
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
  -d '{
    "transactions": [
      {"description": "UBER TRIP", "amount": 15},
      {"description": "NETFLIX MONTHLY", "amount": 14.99}
    ]
  }'
```

### Submit Correction (Improves Personalization)

```bash
curl -X POST http://localhost:8000/api/ml/corrections \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "description": "DOORDASH*THAI FOOD",
    "correct_category": "Food & Dining"
  }'
```

### Chat with AI

```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
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
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "include_transactions": true,
    "include_goals": true,
    "max_recommendations": 5
  }'
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
docker-compose build ai-brain
```

### Start with GPU Support

```bash
# Start all services including AI Brain
docker-compose --profile gpu up -d

# Or start just AI Brain
docker-compose --profile gpu up -d ai-brain

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
│   ├── adapter_model.safetensors # Fine-tuned weights (~100MB)
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

## Fallback Behavior

When the AI Brain is unavailable, the system automatically falls back to:

1. **Transaction Parsing**: Regex-based pattern matching
2. **Chat**: Generic helpful response
3. **Analysis**: Basic statistical summary from context

The fallback is transparent - responses include `confidence: 0.5-0.6` to indicate reduced accuracy.

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

## Configuration

Environment variables for ML/AI:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_STORAGE_PATH` | `./models` | Directory for ML models |
| `AI_BRAIN_ENABLED` | `true` | Enable AI Brain integration |
| `AI_BRAIN_MODE` | `http` | `http` (separate server) or `direct` (in-process) |
| `AI_BRAIN_URL` | `http://localhost:8080` | AI Brain server URL |
| `AI_BRAIN_MODEL_PATH` | `./ai_brain/models/financial-brain-qlora` | Model path for direct mode |

## Performance Considerations

### Tier 1 (Core ML)
- Latency: <10ms per categorization
- Memory: ~50MB for loaded models
- CPU-only, scales horizontally

### Tier 2 (AI Brain)
- Latency: 100-500ms per query
- Memory: 4-8GB VRAM
- GPU required for acceptable performance
- Single instance recommended (model in GPU memory)

## Monitoring

### Cache Statistics
```bash
curl http://localhost:8000/metrics/cache
```

### ML Status
```bash
curl http://localhost:8000/api/ml/status
```

### AI Brain Health
```bash
curl http://localhost:8000/api/ai/status
```
