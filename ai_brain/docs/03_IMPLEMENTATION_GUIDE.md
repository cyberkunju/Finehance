# 🛠️ Implementation Guide: The "Tag & Sum" Architecture

## 1. The Core Philosophy

**"Let AI map the world. Let Code count the cost."**

We do NOT ask the AI to calculate totals. We ask it to **Label** data. This plays to the LLM's strength (semantic understanding) while mitigating its weakness (arithmetic hallucination).

## 2. The Prompt Pattern (Strict Mode)

To integrate this into your backend, use this precise prompt structure. Using `temperature=0.1` is critical for consistency.

### **System Prompt**
```text
You are a transaction classifier.
Your job is to categorize financial transactions into standard categories.
Return ONLY a valid JSON array of objects with keys: "transaction", "category".
Use standard categories:
- "Food & Dining" (includes Groceries, Restaurants, Coffee)
- "Shopping" (includes Retail, Electronics, Amazon)
- "Transportation" (includes Uber, Gas, Public Transit)
- "Utilities" (includes Electric, Water, Internet)
- "Entertainment" (includes Streaming, Movies, Events)
Do not calculate totals. Do not add currency symbols.
```

### **User Input**
```text
Classify these:
Starbucks $6.50
Amazon $234.99
Uber $18.40
```

### **Expected Raw Output**
```json
[
  {"transaction": "Starbucks", "category": "Food & Dining"},
  {"transaction": "Amazon", "category": "Shopping"},
  {"transaction": "Uber", "category": "Transportation"}
]
```

## 3. Python Integration Snippet

Use this function in your valid backend code to bridge the AI and your Database.

```python
import json
from transformers import AutoTokenizer
from peft import AutoPeftModelForCausalLM

class FinancialBrain:
    def __init__(self, model_path):
        # Load model using Peft (Lightweight Adapter)
        self.model = AutoPeftModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            load_in_4bit=True
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

    def classify_transactions(self, transaction_list):
        # 1. Format Input
        text_block = "\n".join([f"{t['desc']} ${t['amount']}" for t in transaction_list])
        
        # 2. Query AI
        prompt = self._build_prompt(text_block)
        raw_response = self._generate(prompt)
        
        # 3. Parse JSON
        try:
            mapping = json.loads(raw_response)
        except:
             # Fallback parsing strategy could go here
             return {}

        # 4. AGGREGATE (The Logic Layer)
        results = {}
        for item in mapping:
            # Find matching original transaction to get exact amount
            # (In production, use IDs)
            original = next((x for x in transaction_list if x['desc'] in item['transaction']), None)
            if original:
                cat = item['category']
                results[cat] = results.get(cat, 0) + original['amount']
        
        return results
```

## 4. Performance Tuning

- **Batching:** Send 10-20 transactions per request. Sending 1 at a time is slow (latency overhead). Sending 100+ might confuse the model's context window.
- **Caching:** Cache the classification of frequent descriptors. "Starbucks" is always "Food & Dining". Don't waste GPU cycles re-classifying it every day.
- **Quantization:** Ensure `load_in_4bit=True` is set, or the model will consume ~14GB VRAM instead of ~2.5GB.
