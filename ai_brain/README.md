# 🧠 Financial AI Brain

**Version:** 1.0 (P100-Optimized)
**Base Model:** Qwen 2.5-3B-Instruct
**Type:** QLoRA Fine-Tune (4-bit)

---

## 📖 Documentation Index

This folder contains the complete technical documentation for the Financial AI Brain project.

1.  [**01_MODEL_ARCHITECTURE.md**](docs/01_MODEL_ARCHITECTURE.md)
    - *What is this model? Why Qwen? Why QLoRA?*
    - Explains the architectural decisions and quantized training methodology.

2.  [**02_DATASET_AND_TRAINING.md**](docs/02_DATASET_AND_TRAINING.md)
    - *How was it trained?*
    - Details the dataset (Sujet Finance), ChatML formatting, and the Kaggle training infrastructure saga (TPU vs GPU).

3.  [**03_IMPLEMENTATION_GUIDE.md**](docs/03_IMPLEMENTATION_GUIDE.md)
    - *How do I use it in my app?*
    - **CRITICAL READ:** Explains the "Tag & Sum" architecture to avoid math hallucinations. Includes Python code snippets.

4.  [**04_PERFORMANCE_REPORT.md**](docs/04_PERFORMANCE_REPORT.md)
    - *Does it actually work?*
    - Comparison results between the Raw Base Model and the Fine-Tuned Brain. Evidence of JSON capability and Persona adoption.

---

## 🚀 Quick Start (Inference)

To run the latest "Strict Mode" test (best practice):

```bash
# Activation
source ~/ai_brain_env/bin/activate
cd ai_brain

# Run Test
python3 test_strict.py
```

## 📂 Directory Structure

```
ai_brain/
├── docs/                 # <--- YOU ARE HERE (Documentation)
├── models/
│   ├── financial-brain-final/  # The Adapter Weights (LoRA)
│   └── test_results.json       # Logs from validation
├── kaggle_notebook/      # The training scripts used on Kaggle
├── compare_models.py     # Script to battle Raw vs Fine-Tuned
├── test_model.py         # General chat capability test
└── test_strict.py        # The "Tag & Sum" architectural validation
```

---

## ⚠️ Known Limitations
1.  **Do not ask for Math:** The model can classify numbers, but should not assume specific sums. Use Python for math.
2.  **Context Window:** Standard 32k context, but for categorization batches, keep it under 2k for speed.
