---
base_model: Qwen/Qwen2.5-3B-Instruct
library_name: peft
pipeline_tag: text-generation
tags:
- base_model:adapter:Qwen/Qwen2.5-3B-Instruct
- lora
- sft
- transformers
- trl
- finance
---

# Finehance Financial Brain — Final LoRA Adapter

This directory contains the final merged/exported LoRA adapter weights for the Finehance Financial AI Brain.

## Details

- **Base model:** Qwen/Qwen2.5-3B-Instruct
- **Adapter type:** LoRA (Low-Rank Adaptation)
- **Training method:** QLoRA (4-bit NF4 quantization during training)
- **Dataset:** Sujet-AI/Sujet-Finance-Instruct-177k (50K curated samples)
- **Training hardware:** NVIDIA Tesla P100 (16GB VRAM) on Kaggle
- **Intended use:** Financial transaction categorization, spending analysis, personalized financial advice

## Relationship to QLoRA Adapter

- `financial-brain-qlora/` — The raw QLoRA adapter checkpoint from training
- `financial-brain-final/` — The final exported adapter weights used for inference

Both directories contain PEFT-compatible adapters that can be loaded with `PeftModel.from_pretrained()`.

## Usage

See the [AI Brain README](../../README.md) and [Implementation Guide](../../docs/03_IMPLEMENTATION_GUIDE.md) for integration details.

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", ...)
model = PeftModel.from_pretrained(model, "./financial-brain-final")
```
