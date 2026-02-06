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

# Finehance Financial Brain — QLoRA Adapter

## Model Details

- **Developed by:** Finehance project (github.com/cyberkunju/Finehance)
- **Model type:** QLoRA adapter (Low-Rank Adaptation)
- **Base model:** Qwen/Qwen2.5-3B-Instruct (3.09B parameters)
- **Language:** English
- **Fine-tuned from:** Qwen/Qwen2.5-3B-Instruct

## Training

- **Dataset:** Sujet-AI/Sujet-Finance-Instruct-177k (50,000 curated samples)
- **Format:** ChatML (system/user/assistant messages)
- **Hardware:** NVIDIA Tesla P100 (16GB VRAM) on Kaggle
- **Training time:** ~7 hours (1 epoch)

### QLoRA Configuration

| Parameter | Value |
|-----------|-------|
| Quantization | 4-bit NF4 |
| Compute dtype | BF16 |
| LoRA rank (r) | 64 |
| LoRA alpha | 128 |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Dropout | 0.05 |

### Training Hyperparameters

| Parameter | Value |
|-----------|-------|
| Epochs | 3 |
| Micro batch size | 2 |
| Gradient accumulation | 8 |
| Effective batch size | 16 |
| Learning rate | 2e-4 |
| LR scheduler | Cosine |
| Max sequence length | 2048 |
| Packing | Enabled |
| Optimizer | AdamW (8-bit) |

## Intended Use

Financial transaction categorization, spending analysis, and personalized financial advice generation for the Finehance platform.

## Performance

| Metric | Raw Model | Fine-Tuned |
|--------|-----------|------------|
| Response format | Verbose text | Pure JSON |
| Categorization accuracy | ~70% | ~95% |
| Tone | Educational/chatty | Professional/analyst |
| Hallucination rate | High | Low (in strict mode) |

## Limitations

- Should not be used for mathematical calculations — use the "Tag & Sum" architecture (LLM classifies, Python computes)
- Optimized for English financial transactions only
- Requires 8GB+ VRAM for inference (RTX 4060/3060 tier)
- Context window: 32K tokens (keep categorization batches under 2K for speed)

## How to Load

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-3B-Instruct",
    quantization_config=quantization_config,
    device_map="auto",
)

model = PeftModel.from_pretrained(base_model, "./financial-brain-qlora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
```
