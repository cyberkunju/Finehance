"""
🧠 UNIFIED FINANCIAL AI BRAIN - INFERENCE SERVICE

High-performance inference server for the fine-tuned Qwen2.5-3B model.
Handles all three modes: Chat, Analysis, and Transaction Parsing.

Optimized for low latency and memory efficiency.
"""

import os
import json
import torch
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import confidence and validation modules
try:
    from .confidence import ConfidenceCalculator, ConfidenceResult
    from .validation import ResponseValidator, ValidationResult

    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    logger.warning("Confidence/validation modules not available - using defaults")


class BrainMode(Enum):
    """Operating modes for the Financial Brain."""

    CHAT = "chat"  # Conversational assistant
    ANALYZE = "analyze"  # Financial analysis
    PARSE = "parse"  # Transaction parsing
    AUTO = "auto"  # Auto-detect mode


@dataclass
class BrainResponse:
    """Response from the Financial Brain."""

    mode: BrainMode
    response: str
    parsed_data: Optional[Dict] = None
    confidence: float = 1.0
    confidence_level: str = "high"  # very_high, high, medium, low, very_low
    processing_time_ms: float = 0.0
    validation_score: float = 1.0
    validation_issues: List[Dict] = field(default_factory=list)
    disclaimer: Optional[str] = None


class FinancialBrain:
    """
    Unified Financial AI Brain

    A fine-tuned LLM that handles:
    - 💬 Conversational finance Q&A
    - 📊 Deep financial analysis
    - 🔍 Transaction parsing
    """

    def __init__(
        self,
        model_path: str = "./models/financial-brain-qlora",
        base_model: str = "Qwen/Qwen2.5-3B-Instruct",
        use_4bit: bool = True,
        max_new_tokens: int = 512,
    ):
        """
        Initialize the Financial Brain.

        Args:
            model_path: Path to the fine-tuned LoRA adapter or merged model
            base_model: Base model to use (if loading adapter)
            use_4bit: Use 4-bit quantization for inference
            max_new_tokens: Maximum tokens to generate
        """
        self.model_path = model_path
        self.base_model = base_model
        self.use_4bit = use_4bit
        self.max_new_tokens = max_new_tokens
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Device: {self.device}")

    def _is_adapter_model(self) -> bool:
        """Check if model_path contains LoRA adapter files."""
        adapter_config = Path(self.model_path) / "adapter_config.json"
        return adapter_config.exists()

    def load_model(self):
        """Load the fine-tuned model."""
        logger.info(f"Loading model from {self.model_path}...")

        is_adapter = self._is_adapter_model()
        if is_adapter:
            logger.info(f"Detected LoRA adapter, base model: {self.base_model}")

        # Use transformers + PEFT (stable and compatible)
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel

        if self.use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        else:
            bnb_config = None

        if is_adapter:
            # Load base model with quantization
            logger.info(f"Loading base model: {self.base_model}")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if not self.use_4bit else None,
            )

            # Load tokenizer from base model (adapter tokenizer may be corrupted)
            logger.info(f"Loading tokenizer from base model: {self.base_model}")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.base_model,
                trust_remote_code=True,
            )

            # Apply LoRA adapter
            logger.info(f"Loading LoRA adapter: {self.model_path}")
            self.model = PeftModel.from_pretrained(self.model, self.model_path)
            self.model.eval()
        else:
            # Load merged model directly
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if not self.use_4bit else None,
            )

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True,
            )

        logger.info("Model loaded successfully with transformers + PEFT")

    def detect_mode(self, query: str) -> BrainMode:
        """
        Auto-detect the appropriate mode based on the query.

        Args:
            query: User query

        Returns:
            Detected mode
        """
        query_lower = query.lower()

        # Check for transaction parsing patterns
        transaction_patterns = [
            r"^[A-Z]{2,}",  # Starts with uppercase letters
            r"\*[A-Z0-9]+",  # Contains * followed by code
            r"#\d+",  # Contains # followed by numbers
            r"parse.*transaction",
            r"what is this transaction",
        ]

        for pattern in transaction_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return BrainMode.PARSE

        # Check for analysis keywords
        analysis_keywords = [
            "analyze",
            "analysis",
            "pattern",
            "trend",
            "insight",
            "report",
            "forecast",
            "predict",
            "breakdown",
            "compare",
            "health score",
            "optimization",
            "optimize",
            "anomaly",
        ]

        if any(keyword in query_lower for keyword in analysis_keywords):
            return BrainMode.ANALYZE

        # Default to chat
        return BrainMode.CHAT

    def build_prompt(
        self,
        query: str,
        mode: BrainMode,
        context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> str:
        """
        Build the prompt for the model.

        Args:
            query: User query
            mode: Operating mode
            context: User financial context
            conversation_history: Previous conversation turns

        Returns:
            Formatted prompt
        """
        # System prompts for each mode
        system_prompts = {
            BrainMode.CHAT: """You are a helpful personal finance AI assistant. You help users understand their finances, provide advice, and answer questions about money management. Be friendly, supportive, and give specific, actionable recommendations based on the user's data.""",
            BrainMode.ANALYZE: """You are an expert financial analyst AI. Provide deep, data-driven insights about the user's finances. Use tables, metrics, and structured analysis. Be thorough and highlight key patterns, risks, and opportunities.""",
            BrainMode.PARSE: """You are a transaction parsing AI. Extract structured information from transaction descriptions. Return valid JSON with: merchant, category, merchant_type, location (if present), is_recurring, and confidence score.""",
        }

        system_msg = system_prompts.get(mode, system_prompts[BrainMode.CHAT])

        # Add context if provided
        if context:
            context_str = self._format_context(context)
            system_msg += f"\n\nUser Financial Context:\n{context_str}"

        # Build conversation
        prompt = f"<|im_start|>system\n{system_msg}<|im_end|>\n"

        # Add conversation history
        if conversation_history:
            for turn in conversation_history:
                role = "user" if turn["role"] == "user" else "assistant"
                prompt += f"<|im_start|>{role}\n{turn['content']}<|im_end|>\n"

        # Add current query
        prompt += f"<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n"

        return prompt

    def _format_context(self, context: Dict) -> str:
        """Format user context as string."""
        parts = []

        if "monthly_income" in context:
            parts.append(f"Monthly Income: ${context['monthly_income']:,}")

        if "spending" in context:
            spending_str = "\n".join(
                [f"  - {cat}: ${amt:,.2f}" for cat, amt in context["spending"].items()]
            )
            parts.append(f"Monthly Spending:\n{spending_str}")

        if "goals" in context:
            goals_str = "\n".join(
                [
                    f"  - {g['name']}: ${g.get('current', 0):,} / ${g['target']:,}"
                    for g in context["goals"]
                ]
            )
            parts.append(f"Goals:\n{goals_str}")

        if "subscriptions" in context:
            parts.append(f"Subscriptions: {context['subscriptions']} active")

        return "\n".join(parts)

    @torch.inference_mode()
    def generate(
        self,
        query: str,
        mode: BrainMode = BrainMode.AUTO,
        context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> BrainResponse:
        """
        Generate a response from the Financial Brain.

        Args:
            query: User query
            mode: Operating mode (or AUTO for auto-detection)
            context: User financial context
            conversation_history: Previous turns
            temperature: Sampling temperature
            top_p: Top-p sampling

        Returns:
            BrainResponse with the generated content
        """
        if self.model is None:
            self.load_model()

        start_time = datetime.now()

        # Auto-detect mode if needed
        if mode == BrainMode.AUTO:
            mode = self.detect_mode(query)

        logger.info(f"Mode: {mode.value}")

        # Build prompt
        prompt = self.build_prompt(query, mode, context, conversation_history)

        # Tokenize
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048 - self.max_new_tokens,
        ).to(self.device)

        # Generate with output scores for confidence calculation
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
            eos_token_id=self.tokenizer.encode("<|im_end|>", add_special_tokens=False)[0],
            output_scores=True,
            return_dict_in_generate=True,
        )

        # Extract generated sequence
        generated_ids = outputs.sequences[0]

        # Decode
        full_response = self.tokenizer.decode(generated_ids, skip_special_tokens=False)

        # Extract assistant response
        response = full_response.split("<|im_start|>assistant\n")[-1]
        response = response.split("<|im_end|>")[0].strip()

        # Calculate real confidence from token probabilities
        confidence = 0.95  # Default fallback
        confidence_level = "high"
        disclaimer = None

        if VALIDATION_AVAILABLE and outputs.scores:
            try:
                # Get only the generated tokens (not input)
                input_length = inputs.input_ids.shape[1]
                generated_token_ids = generated_ids[input_length:].tolist()

                # Calculate confidence from output scores
                confidence_calc = ConfidenceCalculator(temperature=temperature)
                confidence_result = confidence_calc.calculate_from_scores(
                    scores=outputs.scores,
                    generated_ids=generated_token_ids,
                    mode=mode.value,
                )

                confidence = confidence_result.score
                confidence_level = confidence_result.level.value

                # Add disclaimer if needed
                if confidence_calc.should_add_disclaimer(confidence, mode.value):
                    disclaimer = confidence_calc.get_disclaimer_text(confidence, mode.value)

            except Exception as e:
                logger.warning(f"Confidence calculation failed: {e}")

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Parse structured data if in PARSE mode
        parsed_data = None
        if mode == BrainMode.PARSE:
            try:
                # Try to extract JSON from response
                json_match = re.search(r"\{[\s\S]*\}", response)
                if json_match:
                    parsed_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Run validation
        validation_score = 1.0
        validation_issues = []

        if VALIDATION_AVAILABLE:
            try:
                validator = ResponseValidator()
                validation_result = validator.validate(
                    response=response,
                    mode=mode.value,
                    context=context,
                    parsed_data=parsed_data,
                )

                validation_score = validation_result.score
                validation_issues = [i.to_dict() for i in validation_result.issues]

                # Apply category corrections if available
                if validation_result.corrections and parsed_data:
                    for key, value in validation_result.corrections.items():
                        logger.info(f"Applying correction: {key} = {value}")
                        parsed_data[key] = value

            except Exception as e:
                logger.warning(f"Validation failed: {e}")

        return BrainResponse(
            mode=mode,
            response=response,
            parsed_data=parsed_data,
            confidence=confidence,
            confidence_level=confidence_level,
            processing_time_ms=processing_time,
            validation_score=validation_score,
            validation_issues=validation_issues,
            disclaimer=disclaimer,
        )

    async def generate_async(
        self,
        query: str,
        mode: BrainMode = BrainMode.AUTO,
        context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> BrainResponse:
        """Async wrapper for generate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate(query, mode, context, conversation_history)
        )


# =============================================================================
# FASTAPI SERVER
# =============================================================================


def create_api_server():
    """Create FastAPI server for the Financial Brain."""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import Optional, List

    app = FastAPI(
        title="🧠 Financial AI Brain",
        description="Unified AI for financial conversations, analysis, and transaction parsing",
        version="1.0.0",
    )

    # CORS - Restrict to known origins
    # In production, this service is internal-only (accessed by main app, not browsers)
    # Allow configuration via environment variable for flexibility
    cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if cors_origins_env:
        # Parse comma-separated origins or JSON array
        if cors_origins_env.startswith("["):
            import json

            allowed_origins = json.loads(cors_origins_env)
        else:
            allowed_origins = [o.strip() for o in cors_origins_env.split(",")]
    else:
        # Default: Allow main app container and local development
        allowed_origins = [
            "http://localhost:8000",
            "http://localhost:8001",
            "http://ai-finance-dev:8000",
            "http://ai-finance-app:8000",
            "http://dev:8000",
            "http://app:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],  # Only methods actually used
        allow_headers=["Content-Type", "Authorization"],
    )

    # Initialize brain
    brain = FinancialBrain()

    # Request/Response models
    class QueryRequest(BaseModel):
        query: str
        mode: str = "auto"  # auto, chat, analyze, parse
        context: Optional[Dict] = None
        conversation_history: Optional[List[Dict]] = None

    class QueryResponse(BaseModel):
        mode: str
        response: str
        parsed_data: Optional[Dict] = None
        confidence: float
        confidence_level: str = "high"
        processing_time_ms: float
        validation_score: float = 1.0
        validation_issues: List[Dict] = []
        disclaimer: Optional[str] = None

    @app.on_event("startup")
    async def startup():
        """Load model on startup."""
        brain.load_model()

    @app.get("/health")
    async def health():
        return {"status": "healthy", "model_loaded": brain.model is not None}

    @app.get("/metrics")
    async def metrics():
        """Prometheus-compatible metrics endpoint."""
        from fastapi.responses import PlainTextResponse
        model_loaded = 1 if brain.model is not None else 0
        gpu_mem_used = 0
        gpu_mem_total = 0
        if torch.cuda.is_available():
            gpu_mem_used = torch.cuda.memory_allocated()
            gpu_mem_total = torch.cuda.get_device_properties(0).total_mem
        lines = [
            "# HELP ai_brain_up Whether the AI Brain service is up.",
            "# TYPE ai_brain_up gauge",
            f"ai_brain_up 1",
            "# HELP ai_brain_model_loaded Whether the model is loaded.",
            "# TYPE ai_brain_model_loaded gauge",
            f"ai_brain_model_loaded {model_loaded}",
            "# HELP ai_brain_gpu_memory_used_bytes GPU memory used in bytes.",
            "# TYPE ai_brain_gpu_memory_used_bytes gauge",
            f"ai_brain_gpu_memory_used_bytes {gpu_mem_used}",
            "# HELP ai_brain_gpu_memory_total_bytes GPU memory total in bytes.",
            "# TYPE ai_brain_gpu_memory_total_bytes gauge",
            f"ai_brain_gpu_memory_total_bytes {gpu_mem_total}",
            f'# HELP ai_brain_info AI Brain metadata.',
            f'# TYPE ai_brain_info gauge',
            f'ai_brain_info{{model="qwen2.5-3b",version="1.0.0"}} 1',
        ]
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest):
        """Query the Financial Brain."""
        try:
            mode_map = {
                "auto": BrainMode.AUTO,
                "chat": BrainMode.CHAT,
                "analyze": BrainMode.ANALYZE,
                "parse": BrainMode.PARSE,
            }
            mode = mode_map.get(request.mode, BrainMode.AUTO)

            result = await brain.generate_async(
                query=request.query,
                mode=mode,
                context=request.context,
                conversation_history=request.conversation_history,
            )

            return QueryResponse(
                mode=result.mode.value,
                response=result.response,
                parsed_data=result.parsed_data,
                confidence=result.confidence,
                confidence_level=result.confidence_level,
                processing_time_ms=result.processing_time_ms,
                validation_score=result.validation_score,
                validation_issues=result.validation_issues,
                disclaimer=result.disclaimer,
            )
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/chat")
    async def chat(request: QueryRequest):
        """Chat endpoint (alias for query with chat mode)."""
        request.mode = "chat"
        return await query(request)

    @app.post("/analyze")
    async def analyze(request: QueryRequest):
        """Analysis endpoint."""
        request.mode = "analyze"
        return await query(request)

    @app.post("/parse")
    async def parse_transaction(transaction: str):
        """Parse a transaction description."""
        request = QueryRequest(query=transaction, mode="parse")
        return await query(request)

    return app


# =============================================================================
# CLI
# =============================================================================


def interactive_cli():
    """Run interactive CLI for testing."""
    print("=" * 60)
    print("🧠 FINANCIAL AI BRAIN - Interactive Mode")
    print("=" * 60)
    print("Commands: /chat, /analyze, /parse, /quit")
    print("Enter your question or transaction to parse:")
    print()

    brain = FinancialBrain()
    brain.load_model()

    # Sample context
    context = {
        "monthly_income": 5000,
        "spending": {
            "Food & Dining": 800,
            "Transportation": 200,
            "Shopping & Retail": 400,
            "Entertainment": 150,
            "Utilities": 200,
        },
        "goals": [
            {"name": "Emergency Fund", "target": 10000, "current": 3000},
            {"name": "Vacation", "target": 5000, "current": 1500},
        ],
        "subscriptions": 8,
    }

    conversation_history = []
    current_mode = BrainMode.AUTO

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "/quit":
                print("Goodbye! 👋")
                break
            elif user_input.lower() == "/chat":
                current_mode = BrainMode.CHAT
                print("Mode: Chat 💬")
                continue
            elif user_input.lower() == "/analyze":
                current_mode = BrainMode.ANALYZE
                print("Mode: Analysis 📊")
                continue
            elif user_input.lower() == "/parse":
                current_mode = BrainMode.PARSE
                print("Mode: Parse 🔍")
                continue

            # Generate response
            result = brain.generate(
                query=user_input,
                mode=current_mode,
                context=context,
                conversation_history=conversation_history[-4:],  # Keep last 4 turns
            )

            print(f"\n🤖 Brain ({result.mode.value}): {result.response}")
            print(f"   [Time: {result.processing_time_ms:.0f}ms]")

            if result.parsed_data:
                print(f"   [Parsed: {json.dumps(result.parsed_data, indent=2)}]")

            # Update history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": result.response})

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Financial AI Brain")
    parser.add_argument("--server", action="store_true", help="Run as API server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--cli", action="store_true", help="Run interactive CLI")

    args = parser.parse_args()

    if args.server:
        import uvicorn

        app = create_api_server()
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        interactive_cli()


if __name__ == "__main__":
    main()
