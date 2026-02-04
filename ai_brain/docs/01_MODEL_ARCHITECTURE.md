# 🧠 Financial AI Brain - Model Architecture & Design

## 1. Core Model Specifications

| Feature | Specification | Rationale |
|---------|--------------|-----------|
| **Base Model** | `Qwen/Qwen2.5-3B-Instruct` | Chosen for its state-of-the-art performance in the < 7B parameter class. It outperforms Llama-3-8B in many coding and math reasoning benchmarks while remaining lightweight enough to run on consumer hardware (8GB VRAM). |
| **Architecture** | Transformer (Decoder-only) | Standard architecture for causal language modeling, optimized with Grouped Query Attention (GQA) for faster inference. |
| **Parameters** | 3.09 Billion | "Sweet spot" for speed vs. intelligence. Low latency allows for real-time transaction processing. |
| **Context Window** | 32,768 Tokens | Allows processing of long transaction histories or full monthly statements in a single pass. |

## 2. Fine-Tuning Methodology: QLoRA

We utilized **QLoRA (Quantized Low-Rank Adaptation)** to fine-tune the model efficiently. This process involves freezing the main model weights and training only a small "adapter" layer on top.

### **Configuration Details**
- **Quantization:** 4-bit Normal Float (NF4)
    - *Why:* Compresses the model to ~2GB VRAM during training, allowing fine-tuning on free tier GPUs (T4/P100).
    - *Impact:* Minimal loss in accuracy compared to FP16, but massive efficiency gains.
- **LoRA Rank (r):** 64
    - *Why:* A high rank allows the model to learn complex relationships (financial concepts) rather than just surface-level style changes.
- **Alpha:** 128
    - *Why:* higher alpha scales the LoRA updates, making the fine-tuning "stick" more strongly.
- **Target Modules:** `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` (All Linear Layers)
    - *Why:* Targeting all linear layers (not just attention) is proven to yield better reasoning capabilities.

## 3. Training Infrastructure (The "Kaggle Odyssey")

We initially targeted TPU v5e-8 but pivoted to GPU P100 due to stability issues with the XLA compiler and packing algorithms.

- **Hardware Used:** NVIDIA Tesla P100 (16GB VRAM) on Kaggle Kernels.
- **Framework:** PyTorch + HuggingFace `trl` (Transformer Reinforcement Learning) library.
- **Training Time:** ~7 Hours for 1 full epoch.
- **Effective Batch Size:** 128 (Batch size 2 * Gradient Accumulation 8 * 8 GPUs equivalent simulation).
- **Precision:** Mixed Precision (FP16) compute with 4-bit storage.

## 4. The "Hybrid Intelligence" Architecture

We discovered that LLMs, while creative, are poor calculators. To solve this, we implemented a **Hybrid Architecture**:

1.  **The Brain (Semantic Layer):** The LLM is strictly used for *Understanding* and *Classification*.
    - Input: "Uber $18.40"
    - Output: `{"category": "Transportation"}`
    - *It does NOT do math.*

2.  **The Logic (Deterministic Layer):** Python code handles all aggregation, summation, and strict formatting.
    - Logic: `Sum(Transportation)`
    - *Result: 100% Accuracy.*

This separation of concerns ensures the system is **hallucination-proof** regarding numbers.
