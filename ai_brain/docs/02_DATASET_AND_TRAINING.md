# 📊 Dataset & Training Strategy

## 1. The Dataset Strategy

Data quality is the ceiling of model performance. We used a "High Quality, Low Volume" strategy tailored for specific financial tasks.

### **Sources**
1.  **`sujet-ai/Sujet-Finance-Instruct-177k`**: The backbone of our training.
    - A massive instruction-tuning dataset specifically for finance.
    - Contains Q&A pairs on balancing sheets, investment advice, fraud detection, and general financial literacy.
    - *Filter:* We sampled **50,000 high-quality examples** to fit training within strict time limits.

2.  **Synthetic Transaction Data** (Projected):
    - Future fine-tuning will incorporate real user transaction logs (anonymized) to specialize the model further in "Transaction → Category" mapping.

### **Data formatting: ChatML**
We standarized all data into the **ChatML** format, which represents conversation history explicitly. This format is native to the Qwen model family.

**Schema:**
```json
{
  "messages": [
    {"role": "system", "content": "You are a financial AI assistant..."},
    {"role": "user", "content": "Categorize: Starbucks $6.50"},
    {"role": "assistant", "content": "Food & Dining"}
  ]
}
```

**Preprocessing Pipeline:**
1.  **Load:** Ingest `.jsonl` or HuggingFace dataset.
2.  **Map:** Convert heterogeneous column names (e.g., `input`, `response`) into the standard `conversations` list format.
3.  **Tokenize:** Pre-tokenize text using the Qwen tokenizer to ensure valid length (< 2048 tokens).
4.  **Pack:** Use `packing=True` in the trainer to combine short examples into full 2048-token sequences. This makes training ~3x faster by removing padding waste.

## 2. Training Hyperparameters

These settings were tuned for maximum stability on the P100 GPU.

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `learning_rate` | `2e-4` | Standard for QLoRA. prevents "destroying" pre-trained knowledge. |
| `lr_scheduler` | `cosine` | Gradual slowdown of learning rate allows the model to settle into a better optimum. |
| `warmup_ratio` | `0.03` | First 3% of steps gently ramp up LR to prevent divergence at start. |
| `weight_decay` | `0.01` | Regularization to prevent overfitting to the specific training examples. |
| `gradient_accumulation` | `8` | Simulates a large batch size (128) on small hardware, smoothing out noisy gradients. |
| `optim` | `paged_adamw_8bit` | Crucial optimization. Offloads optimizer states to CPU RAM if GPU VRAM fills up, preventing OOM crashes. |

## 3. The "Training Saga" (Lessons Learned)

### **Attempt 1: TPU v5e-8 (The Speed Trap)**
- **Goal:** Use Google's massive TPU pods for lightning-fast training.
- **Result:** Failed.
- **Cause:** The `packing` algorithm runs on CPU before sending data to TPU. With 100k examples, this preprocessing took >2 hours. Kaggle identified the TPU as "Idle" (since preprocessing is CPU-bound) and killed the session automatically.
- **Lesson:** Complex data pipelines (like packing) require careful resource balancing on cloud VMs.

### **Attempt 2: GPU P100 (The Reliable Workhorse)**
- **Goal:** Reliability over raw speed.
- **Adjustment:** Switched to standard CUDA stack. Reduced dataset from 100k to 50k to ensure completion within the 12-hour session limit.
- **Result:** Success. Training completed in ~7 hours with healthy loss convergence (Training loss dropped from ~1.8 to ~0.9).

## 4. Artifacts

The training produced three key artifacts:
1.  **`adapter_model.safetensors`**: The "Financial Brain" weights (approx. 450MB).
2.  **`adapter_config.json`**: The LoRA configuration map.
3.  **Tokenizer Files**: `vocabulary.json` and `merges.txt`, ensuring our text processing matches the model exactly.
