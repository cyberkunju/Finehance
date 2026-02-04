"""
Enhanced Prompt Templates with RAG Support.

Production-quality prompts that incorporate RAG context
for improved accuracy and grounding.
"""

from typing import Dict, List, Optional

# Valid categories for transaction parsing
VALID_CATEGORIES = [
    "Groceries",
    "Fast Food",
    "Restaurants",
    "Coffee & Beverages",
    "Food Delivery",
    "Transportation",
    "Gas & Fuel",
    "Shopping & Retail",
    "Subscriptions",
    "Bills & Utilities",
    "Entertainment",
    "Travel",
    "Healthcare",
    "Insurance",
    "Education",
    "Childcare",
    "Housing",
    "Transfers",
    "Income",
    "Cash & ATM",
    "Convenience",
    "Giving",
    "Other",
]


# =============================================================================
# PARSE MODE PROMPTS
# =============================================================================

PARSE_SYSTEM_PROMPT = """You are an expert transaction parser for a personal finance application.
Your job is to extract structured data from raw bank/card transaction descriptions.

CRITICAL RULES:
1. If MERCHANT DATABASE MATCH is provided, USE THAT INFORMATION - it's from a verified database
2. Extract merchant name, category, amount, and other relevant fields
3. Always return valid JSON matching the schema exactly
4. Confidence should reflect your certainty (0.0-1.0)
5. Use only categories from the VALID_CATEGORIES list

VALID_CATEGORIES:
{categories}

OUTPUT SCHEMA (return ONLY this JSON, no other text):
{{
  "merchant": "string - normalized merchant name",
  "category": "string - one of VALID_CATEGORIES",
  "amount": number or null,
  "is_recurring": boolean,
  "subcategory": "string or null",
  "confidence": number 0.0-1.0
}}""".format(categories=", ".join(VALID_CATEGORIES))


PARSE_USER_TEMPLATE = """
{rag_context}

RAW TRANSACTION TO PARSE:
{transaction}

Return only the JSON object, no additional text.
"""


PARSE_USER_TEMPLATE_NO_RAG = """
Parse this transaction and extract structured data:

{transaction}

Return only the JSON object with merchant, category, amount, is_recurring, and confidence.
"""


# =============================================================================
# CHAT MODE PROMPTS
# =============================================================================

CHAT_SYSTEM_PROMPT = """You are a helpful, knowledgeable personal finance AI assistant.
Help users understand their finances, provide advice, and answer money questions.

CRITICAL RULES:
1. Only reference EXACT numbers from the USER FINANCIAL CONTEXT if provided
2. NEVER fabricate income, account balances, or specific dollar amounts
3. If you don't have specific data, give general advice without inventing numbers
4. Be friendly, supportive, and give actionable recommendations
5. For major financial decisions, recommend consulting a professional
6. Acknowledge uncertainty when appropriate

RESPONSE STYLE:
- Be conversational but informative
- Use bullet points for lists
- Provide specific, actionable next steps
- Include relevant caveats for financial advice
"""


CHAT_USER_TEMPLATE = """
{rag_context}

USER QUESTION:
{query}

Provide helpful, grounded financial advice based only on the information above.
"""


CHAT_USER_TEMPLATE_NO_RAG = """
{query}

(Note: I don't have access to your specific financial data. I'll provide general guidance.)
"""


# =============================================================================
# ANALYZE MODE PROMPTS
# =============================================================================

ANALYZE_SYSTEM_PROMPT = """You are an expert financial analyst AI.
Provide deep, data-driven insights about the user's finances.

CRITICAL RULES:
1. Use ONLY the provided data - never fabricate numbers or statistics
2. Calculate percentages and totals from actual provided values
3. Structure your analysis clearly with sections
4. Highlight key patterns, risks, and opportunities
5. Provide specific, actionable recommendations

ANALYSIS FRAMEWORK:
1. Summary: Key metrics and overview
2. Patterns: Spending trends and behaviors
3. Concerns: Areas needing attention
4. Opportunities: Ways to improve
5. Actions: Specific next steps
"""


ANALYZE_USER_TEMPLATE = """
{rag_context}

ANALYSIS REQUEST:
{query}

Provide a thorough analysis using only the data provided above.
"""


ANALYZE_USER_TEMPLATE_NO_RAG = """
{query}

(Note: Limited financial data available. Provide general analysis framework.)
"""


# =============================================================================
# PROMPT BUILDER
# =============================================================================


class PromptBuilder:
    """
    Build prompts with RAG context integration.

    Usage:
        builder = PromptBuilder()
        system, user = builder.build_parse_prompt(
            transaction="WHOLEFDS 1234",
            rag_context="MERCHANT: Whole Foods..."
        )
    """

    @staticmethod
    def build_parse_prompt(
        transaction: str,
        rag_context: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Build system and user prompts for parse mode.

        Args:
            transaction: Raw transaction description
            rag_context: Formatted RAG context string

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system = PARSE_SYSTEM_PROMPT

        if rag_context:
            user = PARSE_USER_TEMPLATE.format(
                rag_context=rag_context,
                transaction=transaction,
            )
        else:
            user = PARSE_USER_TEMPLATE_NO_RAG.format(
                transaction=transaction,
            )

        return system, user

    @staticmethod
    def build_chat_prompt(
        query: str,
        rag_context: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Build system and user prompts for chat mode.

        Args:
            query: User's question
            rag_context: Formatted RAG context string

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system = CHAT_SYSTEM_PROMPT

        if rag_context:
            user = CHAT_USER_TEMPLATE.format(
                rag_context=rag_context,
                query=query,
            )
        else:
            user = CHAT_USER_TEMPLATE_NO_RAG.format(
                query=query,
            )

        return system, user

    @staticmethod
    def build_analyze_prompt(
        query: str,
        rag_context: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Build system and user prompts for analyze mode.

        Args:
            query: Analysis request
            rag_context: Formatted RAG context string

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system = ANALYZE_SYSTEM_PROMPT

        if rag_context:
            user = ANALYZE_USER_TEMPLATE.format(
                rag_context=rag_context,
                query=query,
            )
        else:
            user = ANALYZE_USER_TEMPLATE_NO_RAG.format(
                query=query,
            )

        return system, user

    @staticmethod
    def format_chatml(
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> str:
        """
        Format prompts into ChatML format for Qwen models.

        Args:
            system_prompt: System message
            user_prompt: User message
            conversation_history: Previous conversation turns

        Returns:
            ChatML formatted prompt string
        """
        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"

        # Add conversation history
        if conversation_history:
            for turn in conversation_history:
                role = "user" if turn["role"] == "user" else "assistant"
                prompt += f"<|im_start|>{role}\n{turn['content']}<|im_end|>\n"

        # Add current user message
        prompt += f"<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"

        return prompt


# Singleton instance
prompt_builder = PromptBuilder()


def build_parse_prompt(transaction: str, rag_context: Optional[str] = None) -> tuple[str, str]:
    """Convenience function for parse prompt building."""
    return prompt_builder.build_parse_prompt(transaction, rag_context)


def build_chat_prompt(query: str, rag_context: Optional[str] = None) -> tuple[str, str]:
    """Convenience function for chat prompt building."""
    return prompt_builder.build_chat_prompt(query, rag_context)


def build_analyze_prompt(query: str, rag_context: Optional[str] = None) -> tuple[str, str]:
    """Convenience function for analyze prompt building."""
    return prompt_builder.build_analyze_prompt(query, rag_context)
