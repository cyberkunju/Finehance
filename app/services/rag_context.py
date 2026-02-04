"""
RAG Context Builder.

Builds enriched context for AI Brain prompts by retrieving relevant
information from merchant databases, user history, and financial knowledge.

RAG = Retrieval-Augmented Generation
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from .merchant_database import MerchantDatabase, MerchantInfo, get_merchant_database
from .merchant_normalizer import MerchantNormalizer, NormalizedTransaction, get_normalizer

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Enriched context for AI generation."""
    
    # Merchant information
    merchant_info: Optional[MerchantInfo] = None
    normalized_transaction: Optional[NormalizedTransaction] = None
    
    # Similar examples
    similar_examples: List[Dict[str, Any]] = field(default_factory=list)
    
    # User context
    user_budget: Optional[Dict[str, Any]] = None
    spending_summary: Optional[Dict[str, Any]] = None
    user_goals: Optional[List[str]] = None
    
    # Category hints
    category_hint: Optional[str] = None
    subcategory_hint: Optional[str] = None
    is_recurring_hint: Optional[bool] = None
    
    # Confidence in the context
    context_confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "merchant_info": self.merchant_info.to_dict() if self.merchant_info else None,
            "normalized": self.normalized_transaction.to_dict() if self.normalized_transaction else None,
            "similar_examples": self.similar_examples,
            "user_budget": self.user_budget,
            "spending_summary": self.spending_summary,
            "user_goals": self.user_goals,
            "category_hint": self.category_hint,
            "subcategory_hint": self.subcategory_hint,
            "is_recurring_hint": self.is_recurring_hint,
            "context_confidence": round(self.context_confidence, 3),
        }


class RAGContextBuilder:
    """
    Build enriched context for AI Brain prompts.
    
    This is the core RAG component that retrieves relevant information
    to inject into prompts, dramatically improving accuracy without
    model retraining.
    
    Usage:
        builder = RAGContextBuilder()
        context = builder.build_parse_context("WHOLEFDS 1234 AUSTIN TX")
        prompt = builder.format_for_parse_prompt(context)
    """
    
    # Few-shot examples for transaction parsing
    PARSE_EXAMPLES = [
        {
            "raw": "AMZN MKTP US*AB12CD $29.99",
            "merchant": "Amazon",
            "category": "Shopping & Retail",
            "amount": 29.99,
        },
        {
            "raw": "WHOLEFDS MKT #10234 AUSTIN TX",
            "merchant": "Whole Foods Market",
            "category": "Groceries",
            "amount": None,
        },
        {
            "raw": "UBER   *TRIP HELP.UBER.C",
            "merchant": "Uber",
            "category": "Transportation",
            "amount": None,
        },
        {
            "raw": "NETFLIX.COM 800-123-4567",
            "merchant": "Netflix",
            "category": "Subscriptions",
            "is_recurring": True,
        },
        {
            "raw": "SQ *COFFEE CORNER",
            "merchant": "Coffee Corner",
            "category": "Coffee & Beverages",
            "payment_processor": "Square",
        },
        {
            "raw": "DOORDASH*CHIPOTLE",
            "merchant": "DoorDash - Chipotle",
            "category": "Food Delivery",
            "amount": None,
        },
        {
            "raw": "SHELL OIL 12345678",
            "merchant": "Shell",
            "category": "Gas & Fuel",
            "amount": None,
        },
        {
            "raw": "COSTCO WHSE #1234",
            "merchant": "Costco",
            "category": "Groceries",
            "subcategory": "Warehouse Club",
        },
    ]
    
    # Financial guidance context
    FINANCIAL_GUIDELINES = """
IMPORTANT GUIDELINES:
- Only use exact values from the user's data - never fabricate amounts
- Categories must be from the valid list: Groceries, Fast Food, Restaurants, 
  Coffee & Beverages, Food Delivery, Transportation, Gas & Fuel, Shopping & Retail,
  Subscriptions, Bills & Utilities, Entertainment, Travel, Healthcare, Insurance,
  Education, Housing, Transfers, Income, Cash & ATM, Other
- If merchant info is provided from database, trust it
- For unknown merchants, use context clues from the description
- Confidence should reflect certainty (0.0-1.0)
"""
    
    def __init__(
        self,
        merchant_db: Optional[MerchantDatabase] = None,
        normalizer: Optional[MerchantNormalizer] = None,
    ):
        """
        Initialize the RAG context builder.
        
        Args:
            merchant_db: Merchant database instance
            normalizer: Merchant normalizer instance
        """
        self.merchant_db = merchant_db or get_merchant_database()
        self.normalizer = normalizer or get_normalizer()
    
    def build_parse_context(
        self,
        raw_transaction: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> RAGContext:
        """
        Build context for transaction parsing.
        
        Args:
            raw_transaction: Raw transaction description
            user_context: Optional user financial context
            
        Returns:
            RAGContext with merchant info, examples, and hints
        """
        context = RAGContext()
        
        # 1. Normalize the transaction
        context.normalized_transaction = self.normalizer.normalize(raw_transaction)
        
        # 2. Look up merchant in database
        context.merchant_info = self.merchant_db.lookup(raw_transaction)
        
        # 3. Set category hints from merchant info
        if context.merchant_info:
            context.category_hint = context.merchant_info.category
            context.subcategory_hint = context.merchant_info.subcategory
            context.is_recurring_hint = context.merchant_info.is_recurring
            context.context_confidence = context.merchant_info.match_score
        else:
            context.context_confidence = 0.5  # Lower confidence without DB match
        
        # 4. Find similar examples
        context.similar_examples = self._find_similar_examples(
            raw_transaction,
            context.category_hint,
        )
        
        # 5. Add user context if provided
        if user_context:
            context.user_budget = user_context.get("budget")
            context.spending_summary = user_context.get("spending_summary")
            context.user_goals = user_context.get("goals")
        
        return context
    
    def build_chat_context(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
        transaction_data: Optional[List[Dict]] = None,
    ) -> RAGContext:
        """
        Build context for chat/advice mode.
        
        Args:
            query: User's question
            user_context: User's financial context
            transaction_data: Recent transactions for context
            
        Returns:
            RAGContext for chat generation
        """
        context = RAGContext()
        
        # Add user context
        if user_context:
            context.user_budget = user_context.get("budget")
            context.spending_summary = user_context.get("spending_summary")
            context.user_goals = user_context.get("goals")
        
        # High confidence if we have user data
        if user_context:
            context.context_confidence = 0.9
        else:
            context.context_confidence = 0.5
        
        return context
    
    def build_analyze_context(
        self,
        transactions: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> RAGContext:
        """
        Build context for transaction analysis mode.
        
        Args:
            transactions: List of transactions to analyze
            user_context: User's financial context
            
        Returns:
            RAGContext for analysis
        """
        context = RAGContext()
        
        # Add user context
        if user_context:
            context.user_budget = user_context.get("budget")
            context.spending_summary = user_context.get("spending_summary")
            context.user_goals = user_context.get("goals")
            context.context_confidence = 0.9
        else:
            context.context_confidence = 0.7
        
        return context
    
    def _find_similar_examples(
        self,
        raw_transaction: str,
        category_hint: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        Find similar examples for few-shot learning.
        
        Returns examples that match the category or have similar structure.
        """
        examples = []
        
        # If we have a category hint, prioritize examples from that category
        if category_hint:
            for ex in self.PARSE_EXAMPLES:
                if ex.get("category") == category_hint:
                    examples.append(ex)
                    if len(examples) >= 2:
                        break
        
        # Add a couple diverse examples
        for ex in self.PARSE_EXAMPLES:
            if ex not in examples:
                examples.append(ex)
                if len(examples) >= 4:
                    break
        
        return examples
    
    def format_for_parse_prompt(self, context: RAGContext) -> str:
        """
        Format RAG context as a string for injection into parse prompt.
        
        Args:
            context: RAGContext to format
            
        Returns:
            Formatted string for prompt injection
        """
        parts = []
        
        # Merchant database info (highest value)
        if context.merchant_info:
            parts.append("MERCHANT DATABASE MATCH (trust this information):")
            parts.append(f"  Canonical Name: {context.merchant_info.canonical_name}")
            parts.append(f"  Category: {context.merchant_info.category}")
            if context.merchant_info.subcategory:
                parts.append(f"  Subcategory: {context.merchant_info.subcategory}")
            parts.append(f"  Is Recurring: {context.merchant_info.is_recurring}")
            if context.merchant_info.typical_amounts:
                parts.append(f"  Typical Amounts: {context.merchant_info.typical_amounts}")
            parts.append(f"  Match Confidence: {context.merchant_info.match_score:.0%}")
            parts.append("")
        
        # Normalized transaction info
        if context.normalized_transaction:
            normalized = context.normalized_transaction
            parts.append("NORMALIZED TRANSACTION:")
            parts.append(f"  Extracted Merchant: {normalized.merchant_name}")
            if normalized.amount:
                parts.append(f"  Extracted Amount: ${normalized.amount:.2f}")
            if normalized.location:
                parts.append(f"  Location: {normalized.location}")
            if normalized.payment_processor:
                parts.append(f"  Payment Processor: {normalized.payment_processor}")
            parts.append("")
        
        # Similar examples
        if context.similar_examples:
            parts.append("SIMILAR TRANSACTIONS (for reference):")
            for ex in context.similar_examples[:3]:
                parsed = {
                    "merchant": ex.get("merchant"),
                    "category": ex.get("category"),
                }
                if ex.get("amount"):
                    parsed["amount"] = ex["amount"]
                parts.append(f"  Input: \"{ex['raw']}\"")
                parts.append(f"  Output: {json.dumps(parsed)}")
            parts.append("")
        
        # Guidelines
        parts.append(self.FINANCIAL_GUIDELINES)
        
        return "\n".join(parts)
    
    def format_for_chat_prompt(self, context: RAGContext) -> str:
        """
        Format RAG context for chat/advice prompt.
        
        Args:
            context: RAGContext to format
            
        Returns:
            Formatted string for prompt injection
        """
        parts = []
        
        # User's financial context
        if context.user_budget:
            parts.append("USER'S BUDGET:")
            for category, amount in context.user_budget.items():
                parts.append(f"  {category}: ${amount:.2f}")
            parts.append("")
        
        if context.spending_summary:
            parts.append("RECENT SPENDING SUMMARY:")
            for category, data in context.spending_summary.items():
                if isinstance(data, dict):
                    total = data.get("total", 0)
                    parts.append(f"  {category}: ${total:.2f}")
                else:
                    parts.append(f"  {category}: ${data:.2f}")
            parts.append("")
        
        if context.user_goals:
            parts.append("FINANCIAL GOALS:")
            for goal in context.user_goals:
                parts.append(f"  - {goal}")
            parts.append("")
        
        # Guidelines for chat
        parts.append("""
IMPORTANT:
- Only reference the exact numbers provided above
- If you don't have specific data, say "Based on the information available..."
- Never fabricate account balances, income, or specific amounts
- Provide actionable advice but recommend consulting professionals for major decisions
""")
        
        return "\n".join(parts)
    
    def format_for_analyze_prompt(self, context: RAGContext) -> str:
        """
        Format RAG context for analysis prompt.
        
        Args:
            context: RAGContext to format
            
        Returns:
            Formatted string for prompt injection
        """
        parts = []
        
        if context.user_budget:
            parts.append("BUDGET LIMITS:")
            for category, amount in context.user_budget.items():
                parts.append(f"  {category}: ${amount:.2f}")
            parts.append("")
        
        if context.spending_summary:
            parts.append("SPENDING BY CATEGORY:")
            for category, data in context.spending_summary.items():
                if isinstance(data, dict):
                    total = data.get("total", 0)
                    count = data.get("count", 0)
                    parts.append(f"  {category}: ${total:.2f} ({count} transactions)")
                else:
                    parts.append(f"  {category}: ${data:.2f}")
            parts.append("")
        
        parts.append("""
ANALYSIS GUIDELINES:
- Compare spending to budget limits
- Identify categories over/under budget
- Calculate percentages using provided numbers only
- Do not assume or fabricate any financial data
""")
        
        return "\n".join(parts)


# Singleton instance
_rag_builder: Optional[RAGContextBuilder] = None


def get_rag_builder() -> RAGContextBuilder:
    """Get the singleton RAGContextBuilder instance."""
    global _rag_builder
    if _rag_builder is None:
        _rag_builder = RAGContextBuilder()
    return _rag_builder


def build_context_for_parse(
    raw_transaction: str,
    user_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Convenience function to build and format parse context.
    
    Args:
        raw_transaction: Raw transaction description
        user_context: Optional user context
        
    Returns:
        Formatted context string for prompt
    """
    builder = get_rag_builder()
    context = builder.build_parse_context(raw_transaction, user_context)
    return builder.format_for_parse_prompt(context)


def build_context_for_chat(
    query: str,
    user_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Convenience function to build and format chat context.
    
    Args:
        query: User's question
        user_context: User's financial context
        
    Returns:
        Formatted context string for prompt
    """
    builder = get_rag_builder()
    context = builder.build_chat_context(query, user_context)
    return builder.format_for_chat_prompt(context)


def enrich_transaction(raw_transaction: str) -> Dict[str, Any]:
    """
    Get enriched information about a transaction.
    
    Combines normalization and database lookup for comprehensive info.
    
    Args:
        raw_transaction: Raw transaction description
        
    Returns:
        Dictionary with all extracted/retrieved information
    """
    builder = get_rag_builder()
    context = builder.build_parse_context(raw_transaction)
    return context.to_dict()
