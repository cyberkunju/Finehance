"""
OmniBar Service — Universal Natural Language Command Engine.

This is the brain behind the OmniBar: a single text input that understands
any natural-language instruction related to the finance platform.

Capabilities:
  1. ADD_TRANSACTION  — "Had 2 sandwiches yesterday at 2pm, cost 250rs"
  2. ADD_GOAL         — "I want to save 50000 for a laptop by December"
  3. ADD_BUDGET       — "Set a food budget of 5000 for this month"
  4. QUERY_SPENDING   — "How much did I spend on food last month?"
  5. QUERY_GOAL       — "How close am I to my laptop goal?"
  6. QUERY_BUDGET     — "Am I over budget on entertainment?"
  7. QUERY_GENERAL    — "What's my savings rate?"
  8. CHAT             — General financial advice / conversation

The service uses the AI Brain (fine-tuned LLM) for intent classification
and entity extraction, then dispatches to the appropriate domain service
to execute the action or query.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Intent Classification
# =============================================================================


class OmniIntent(str, Enum):
    """All intents the OmniBar can handle."""

    ADD_TRANSACTION = "add_transaction"
    ADD_GOAL = "add_goal"
    ADD_BUDGET = "add_budget"
    UPDATE_GOAL_PROGRESS = "update_goal_progress"
    QUERY_SPENDING = "query_spending"
    QUERY_GOAL = "query_goal"
    QUERY_BUDGET = "query_budget"
    QUERY_GENERAL = "query_general"
    CHAT = "chat"


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: OmniIntent
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class OmniResponse:
    """Unified response from the OmniBar engine."""

    success: bool
    message: str
    intent: str
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    confidence: float = 1.0


# =============================================================================
# Intent Classifier (Rule-based + AI hybrid)
# =============================================================================


class IntentClassifier:
    """
    Hybrid intent classifier.

    Uses fast rule-based matching first for common patterns,
    then falls back to the AI Brain for ambiguous inputs.
    """

    # Pattern groups for rule-based classification
    ADD_TRANSACTION_PATTERNS = [
        r"\b(spent|paid|bought|purchased|cost|had|ate|ordered|subscribed|charged)\b",
        r"\b(rs|₹|\$|rupee|dollar|usd|inr)\s*\d+",
        r"\d+\s*(rs|₹|\$|rupee|dollar|usd|inr)\b",
        r"\b(expense|transaction|payment|bill)\b.*\b(add|create|log|record|enter)\b",
        r"\b(add|create|log|record|enter)\b.*\b(expense|transaction|payment|bill)\b",
    ]

    ADD_GOAL_PATTERNS = [
        r"\b(save|saving|goal|target)\b.*\b(for|towards|by)\b",
        r"\b(want to|wanna|need to|planning to)\b.*\b(save|buy|achieve|reach)\b",
        r"\b(set|create|add|new)\b.*\b(goal|target|savings)\b",
    ]

    ADD_BUDGET_PATTERNS = [
        r"\b(set|create|add|make|define)\b.*\b(budget|limit|cap|ceiling)\b",
        r"\b(budget|limit|cap)\b.*\b(set|create|add|make)\b",
        r"\b(allocate|assign)\b.*\b(budget|amount)\b",
    ]

    UPDATE_GOAL_PATTERNS = [
        r"\b(saved|deposited|added|contributed|put)\b.*\b(towards|to|for|into)\b.*\b(goal|saving|target)\b",
        r"\b(goal|saving|target)\b.*\b(update|progress|added)\b",
    ]

    QUERY_SPENDING_PATTERNS = [
        r"\b(how much|what|total|sum)\b.*\b(spend|spent|spending|expense|expenses)\b",
        r"\b(spend|spent|spending|expense)\b.*\b(how much|what|total|on)\b",
        r"\b(show|display|tell|give)\b.*\b(spend|spent|expense|expenses)\b",
        r"\b(last|this|previous)\b.*\b(month|week|year|day)\b.*\b(spend|spent|spending)\b",
    ]

    QUERY_GOAL_PATTERNS = [
        r"\b(how|what|show|display)\b.*\b(goal|goals|target|saving|savings)\b",
        r"\b(goal|target|savings?)\b.*\b(progress|status|close|far|remaining|left)\b",
        r"\b(close|far|near)\b.*\b(goal|target)\b",
    ]

    QUERY_BUDGET_PATTERNS = [
        r"\b(how|what|show|am i|are we)\b.*\b(budget|budgets)\b",
        r"\b(budget)\b.*\b(status|progress|over|under|left|remaining)\b",
        r"\b(over|under)\b.*\b(budget)\b",
    ]

    QUERY_GENERAL_PATTERNS = [
        r"\b(savings rate|net worth|income|total|summary|overview|report)\b",
        r"\b(how much|what is|show me|tell me)\b.*\b(balance|income|earning|net)\b",
        r"\b(average|monthly|weekly|daily)\b.*\b(spend|expense|earning|income)\b",
    ]

    def classify(self, text: str) -> IntentResult:
        """
        Classify user input into an intent.

        Uses pattern matching with confidence scoring.
        """
        text_lower = text.lower().strip()

        # Score each intent
        scores: Dict[OmniIntent, float] = {}

        scores[OmniIntent.ADD_TRANSACTION] = self._score_patterns(
            text_lower, self.ADD_TRANSACTION_PATTERNS
        )
        scores[OmniIntent.ADD_GOAL] = self._score_patterns(
            text_lower, self.ADD_GOAL_PATTERNS
        )
        scores[OmniIntent.ADD_BUDGET] = self._score_patterns(
            text_lower, self.ADD_BUDGET_PATTERNS
        )
        scores[OmniIntent.UPDATE_GOAL_PROGRESS] = self._score_patterns(
            text_lower, self.UPDATE_GOAL_PATTERNS
        )
        scores[OmniIntent.QUERY_SPENDING] = self._score_patterns(
            text_lower, self.QUERY_SPENDING_PATTERNS
        )
        scores[OmniIntent.QUERY_GOAL] = self._score_patterns(
            text_lower, self.QUERY_GOAL_PATTERNS
        )
        scores[OmniIntent.QUERY_BUDGET] = self._score_patterns(
            text_lower, self.QUERY_BUDGET_PATTERNS
        )
        scores[OmniIntent.QUERY_GENERAL] = self._score_patterns(
            text_lower, self.QUERY_GENERAL_PATTERNS
        )

        # Find best match
        best_intent = max(scores, key=scores.get)  # type: ignore
        best_score = scores[best_intent]

        if best_score < 0.3:
            # No strong match — treat as general chat
            return IntentResult(
                intent=OmniIntent.CHAT,
                confidence=0.5,
                raw_text=text,
            )

        # Extract entities based on intent
        entities = self._extract_entities(text, text_lower, best_intent)

        return IntentResult(
            intent=best_intent,
            confidence=min(best_score, 1.0),
            entities=entities,
            raw_text=text,
        )

    def _score_patterns(self, text: str, patterns: List[str]) -> float:
        """Score how well text matches a set of patterns."""
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        if matches == 0:
            return 0.0
        # Any single match gives a strong signal (0.5+), more matches boost further
        return min(0.5 + (matches - 1) * 0.15, 1.0)

    def _extract_entities(
        self, text: str, text_lower: str, intent: OmniIntent
    ) -> Dict[str, Any]:
        """Extract relevant entities based on intent."""
        entities: Dict[str, Any] = {}

        if intent in (OmniIntent.ADD_TRANSACTION, OmniIntent.QUERY_SPENDING):
            # Extract amount
            amount = self._extract_amount(text)
            if amount:
                entities["amount"] = amount

            # Extract date
            parsed_date = self._extract_date(text_lower)
            if parsed_date:
                entities["date"] = parsed_date.isoformat()

            # Extract time
            parsed_time = self._extract_time(text_lower)
            if parsed_time:
                entities["time"] = parsed_time

            # Extract category hints
            category = self._extract_category(text_lower)
            if category:
                entities["category"] = category

            # Extract description (the item/service mentioned)
            description = self._extract_description(text, intent)
            if description:
                entities["description"] = description

            # Extract quantity
            qty = self._extract_quantity(text_lower)
            if qty:
                entities["quantity"] = qty

            # Time period for queries
            if intent == OmniIntent.QUERY_SPENDING:
                period = self._extract_time_period(text_lower)
                if period:
                    entities["period_start"] = period[0].isoformat()
                    entities["period_end"] = period[1].isoformat()

        elif intent in (OmniIntent.ADD_GOAL, OmniIntent.QUERY_GOAL):
            amount = self._extract_amount(text)
            if amount:
                entities["target_amount"] = amount

            # Extract goal name / purpose
            purpose = self._extract_goal_purpose(text_lower)
            if purpose:
                entities["name"] = purpose

            # Extract deadline
            deadline = self._extract_deadline(text_lower)
            if deadline:
                entities["deadline"] = deadline.isoformat()

        elif intent in (OmniIntent.ADD_BUDGET, OmniIntent.QUERY_BUDGET):
            amount = self._extract_amount(text)
            if amount:
                entities["amount"] = amount

            category = self._extract_category(text_lower)
            if category:
                entities["category"] = category

            period = self._extract_time_period(text_lower)
            if period:
                entities["period_start"] = period[0].isoformat()
                entities["period_end"] = period[1].isoformat()

        elif intent == OmniIntent.UPDATE_GOAL_PROGRESS:
            amount = self._extract_amount(text)
            if amount:
                entities["amount"] = amount

            purpose = self._extract_goal_purpose(text_lower)
            if purpose:
                entities["goal_name"] = purpose

        return entities

    # ---- Entity extraction helpers ----

    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract monetary amount from text."""
        patterns = [
            r'(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d{1,2})?)',  # Rs 250, ₹250, ₹1500
            r'([\d,]+(?:\.\d{1,2})?)\s*(?:rs\.?|₹|rupees?|inr)',  # 250 Rs
            r'\$([\d,]+(?:\.\d{1,2})?)',  # $250
            r'([\d,]+(?:\.\d{1,2})?)\s*(?:dollars?|usd)',  # 250 dollars
            r'\b(?:cost|costs?|costed|paid|spent|for|price|worth|was|is)\s+(?:rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)',
            r'([\d,]+(?:\.\d{1,2})?)\s*(?:bucks|per)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Get the last group that matched (some patterns have nested groups)
                amount_str = None
                for g in reversed(match.groups()):
                    if g and re.match(r'^[\d,]+(?:\.\d+)?$', g):
                        amount_str = g
                        break
                if amount_str:
                    amount_str = amount_str.replace(",", "")
                    try:
                        val = float(amount_str)
                        if val > 0:
                            return val
                    except ValueError:
                        continue

        # Fallback: look for standalone numbers that could be amounts
        # Check for financial context words
        financial_words = [
            "spent", "paid", "cost", "bought", "price", "worth", "charged",
            "expense", "save", "saving", "budget", "goal", "target", "saved",
            "added", "deposited", "salary", "earned", "income",
        ]
        text_lower = text.lower()
        if any(w in text_lower for w in financial_words):
            # Find all numbers >= 2 digits (likely amounts, not quantities)
            numbers = re.findall(r'\b([\d,]+(?:\.\d{1,2})?)\b', text)
            # Filter out small numbers that are likely quantities
            for num_str in numbers:
                try:
                    val = float(num_str.replace(",", ""))
                    if val >= 10:  # Likely an amount, not a quantity
                        return val
                except ValueError:
                    continue

        return None

    def _extract_date(self, text: str) -> Optional[date]:
        """Extract date from natural language."""
        today = date.today()

        # Relative dates
        if "today" in text:
            return today
        if "yesterday" in text:
            return today - timedelta(days=1)
        if "day before yesterday" in text:
            return today - timedelta(days=2)
        if "tomorrow" in text:
            return today + timedelta(days=1)

        # "last monday", "last friday", etc.
        days_of_week = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        for day_name, day_num in days_of_week.items():
            if f"last {day_name}" in text:
                days_back = (today.weekday() - day_num) % 7
                if days_back == 0:
                    days_back = 7
                return today - timedelta(days=days_back)
            if day_name in text and "last" not in text:
                # This week's day
                days_forward = (day_num - today.weekday()) % 7
                if days_forward == 0 and "next" not in text:
                    return today  # Today is that day
                return today + timedelta(days=days_forward)

        # "N days ago"
        match = re.search(r"(\d+)\s*days?\s*ago", text)
        if match:
            return today - timedelta(days=int(match.group(1)))

        # Explicit dates: "Jan 15", "15th January", "2024-01-15", "15/01/2024"
        # MM/DD or DD/MM format
        match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", text)
        if match:
            d1, d2 = int(match.group(1)), int(match.group(2))
            year = int(match.group(3)) if match.group(3) else today.year
            if year < 100:
                year += 2000
            # Try DD/MM/YYYY first (more common internationally)
            try:
                return date(year, d2, d1)
            except ValueError:
                try:
                    return date(year, d1, d2)
                except ValueError:
                    pass

        # "January 15" or "15 January" or "Jan 15th"
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            "january": 1, "february": 2, "march": 3, "april": 4,
            "june": 6, "july": 7, "august": 8, "september": 9,
            "october": 10, "november": 11, "december": 12,
        }
        for month_name, month_num in months.items():
            # "Jan 15" or "Jan 15th"
            match = re.search(
                rf"\b{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", text
            )
            if match:
                day = int(match.group(1))
                try:
                    return date(today.year, month_num, day)
                except ValueError:
                    pass

            # "15 Jan" or "15th Jan"
            match = re.search(
                rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{month_name}\b", text
            )
            if match:
                day = int(match.group(1))
                try:
                    return date(today.year, month_num, day)
                except ValueError:
                    pass

        # Default to today if no date found
        return None

    def _extract_time(self, text: str) -> Optional[str]:
        """Extract time from text."""
        # "2pm", "2:30pm", "14:30", "2 pm"
        match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)", text
        )
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            ampm = match.group(3).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute:02d}"

        # 24hr format: "14:30"
        match = re.search(r"\b(\d{2}):(\d{2})\b", text)
        if match:
            return f"{match.group(1)}:{match.group(2)}"

        return None

    def _extract_category(self, text: str) -> Optional[str]:
        """Extract spending category from text."""
        category_map = {
            "food": "Food & Dining",
            "lunch": "Food & Dining",
            "dinner": "Food & Dining",
            "breakfast": "Food & Dining",
            "snack": "Food & Dining",
            "sandwich": "Food & Dining",
            "pizza": "Food & Dining",
            "burger": "Food & Dining",
            "biryani": "Food & Dining",
            "meal": "Food & Dining",
            "restaurant": "Restaurants",
            "cafe": "Coffee & Beverages",
            "coffee": "Coffee & Beverages",
            "tea": "Coffee & Beverages",
            "starbucks": "Coffee & Beverages",
            "grocery": "Groceries",
            "groceries": "Groceries",
            "vegetable": "Groceries",
            "fruit": "Groceries",
            "supermarket": "Groceries",
            "uber": "Transportation",
            "ola": "Transportation",
            "cab": "Transportation",
            "taxi": "Transportation",
            "bus": "Transportation",
            "train": "Transportation",
            "metro": "Transportation",
            "auto": "Transportation",
            "rickshaw": "Transportation",
            "fuel": "Gas & Fuel",
            "petrol": "Gas & Fuel",
            "diesel": "Gas & Fuel",
            "gas": "Gas & Fuel",
            "netflix": "Subscriptions",
            "spotify": "Subscriptions",
            "subscription": "Subscriptions",
            "amazon prime": "Subscriptions",
            "hotstar": "Subscriptions",
            "youtube premium": "Subscriptions",
            "movie": "Entertainment",
            "cinema": "Entertainment",
            "game": "Entertainment",
            "entertainment": "Entertainment",
            "electricity": "Bills & Utilities",
            "electric": "Bills & Utilities",
            "water bill": "Bills & Utilities",
            "internet": "Bills & Utilities",
            "wifi": "Bills & Utilities",
            "phone bill": "Bills & Utilities",
            "recharge": "Bills & Utilities",
            "rent": "Housing",
            "housing": "Housing",
            "emi": "Housing",
            "mortgage": "Housing",
            "doctor": "Healthcare",
            "hospital": "Healthcare",
            "medicine": "Healthcare",
            "medical": "Healthcare",
            "pharmacy": "Healthcare",
            "health": "Healthcare",
            "insurance": "Insurance",
            "school": "Education",
            "college": "Education",
            "course": "Education",
            "tuition": "Education",
            "book": "Education",
            "udemy": "Education",
            "travel": "Travel",
            "flight": "Travel",
            "hotel": "Travel",
            "trip": "Travel",
            "vacation": "Travel",
            "shopping": "Shopping & Retail",
            "clothes": "Shopping & Retail",
            "shoes": "Shopping & Retail",
            "amazon": "Shopping & Retail",
            "flipkart": "Shopping & Retail",
            "myntra": "Shopping & Retail",
            "electronics": "Shopping & Retail",
            "gadget": "Shopping & Retail",
            "laptop": "Shopping & Retail",
            "phone": "Shopping & Retail",
            "mobile": "Shopping & Retail",
            "salary": "Income",
            "freelance": "Income",
            "income": "Income",
            "earned": "Income",
            "atm": "Cash & ATM",
            "cash": "Cash & ATM",
            "withdrew": "Cash & ATM",
            "withdrawal": "Cash & ATM",
            "doordash": "Food Delivery",
            "zomato": "Food Delivery",
            "swiggy": "Food Delivery",
            "delivery": "Food Delivery",
            "fast food": "Fast Food",
            "mcdonalds": "Fast Food",
            "kfc": "Fast Food",
        }

        # Check for multi-word categories first (longest match)
        for keyword, category in sorted(
            category_map.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if keyword in text:
                return category

        return None

    def _extract_description(self, text: str, intent: OmniIntent) -> Optional[str]:
        """Extract a description/item from the text."""
        # Remove common action words to find the "what"
        cleaned = re.sub(
            r"\b(i |i've |had |bought |purchased |spent |paid |cost |costs? |"
            r"yesterday |today |tomorrow |last |this |at |on |for |the |a |an |"
            r"was |is |it |my |me |rs\.? |₹ |\$ |rupees? |dollars? )\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        # Remove amounts
        cleaned = re.sub(r"[\d,]+(?:\.\d+)?", " ", cleaned)
        # Remove times
        cleaned = re.sub(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)", " ", cleaned, flags=re.IGNORECASE)
        # Clean up whitespace
        cleaned = " ".join(cleaned.split()).strip()

        if cleaned and len(cleaned) > 1:
            return cleaned.title()

        return text.strip()[:100]  # Fallback to truncated original text

    def _extract_quantity(self, text: str) -> Optional[int]:
        """Extract quantity from text like '2 sandwiches'."""
        match = re.search(r"(\d+)\s+(?!rs|₹|\$|rupee|dollar|am|pm)\w+", text)
        if match:
            qty = int(match.group(1))
            if 1 < qty <= 100:  # Reasonable quantity range
                return qty
        return None

    def _extract_time_period(self, text: str) -> Optional[tuple]:
        """Extract time period (start_date, end_date) from text."""
        today = date.today()

        if "this month" in text:
            start = today.replace(day=1)
            return (start, today)

        if "last month" in text:
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return (last_month_start, last_month_end)

        if "this week" in text:
            start = today - timedelta(days=today.weekday())
            return (start, today)

        if "last week" in text:
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
            return (start, end)

        if "this year" in text:
            start = date(today.year, 1, 1)
            return (start, today)

        if "last year" in text:
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
            return (start, end)

        # "last N days/months"
        match = re.search(r"last\s+(\d+)\s+(day|week|month|year)s?", text)
        if match:
            n = int(match.group(1))
            unit = match.group(2)
            if unit == "day":
                start = today - timedelta(days=n)
            elif unit == "week":
                start = today - timedelta(weeks=n)
            elif unit == "month":
                start = today - timedelta(days=n * 30)
            elif unit == "year":
                start = today - timedelta(days=n * 365)
            else:
                start = today - timedelta(days=30)
            return (start, today)

        return None

    def _extract_goal_purpose(self, text: str) -> Optional[str]:
        """Extract the purpose/name for a goal."""
        # "save for a laptop", "save for vacation"
        match = re.search(r"\b(?:for|towards|to buy|to get)\s+(?:a\s+)?(.+?)(?:\s+by|\s+in|\s+within|\s+before|$)", text)
        if match:
            purpose = match.group(1).strip()
            # Clean common trailing words
            purpose = re.sub(r"\s+(?:this|next|the|within|before)\s+.*$", "", purpose)
            if purpose:
                return purpose.title()

        return None

    def _extract_deadline(self, text: str) -> Optional[date]:
        """Extract a deadline date from text."""
        today = date.today()
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "jun": 6, "jul": 7, "aug": 8, "sep": 9,
            "oct": 10, "nov": 11, "dec": 12,
        }

        # "by December", "by March 2025"
        for month_name, month_num in months.items():
            match = re.search(
                rf"\bby\s+{month_name}(?:\s+(\d{{4}}))?\b", text
            )
            if match:
                year = int(match.group(1)) if match.group(1) else today.year
                if month_num <= today.month and year == today.year:
                    year += 1  # Next year if month already passed
                try:
                    # Last day of that month
                    if month_num == 12:
                        return date(year, 12, 31)
                    return date(year, month_num + 1, 1) - timedelta(days=1)
                except ValueError:
                    pass

        # "in N months"
        match = re.search(r"\bin\s+(\d+)\s+months?\b", text)
        if match:
            months_ahead = int(match.group(1))
            future = today + timedelta(days=months_ahead * 30)
            return future

        # "in N years"
        match = re.search(r"\bin\s+(\d+)\s+years?\b", text)
        if match:
            years_ahead = int(match.group(1))
            try:
                return today.replace(year=today.year + years_ahead)
            except ValueError:
                return date(today.year + years_ahead, today.month, 28)

        return None


# =============================================================================
# OmniBar Executor — Dispatches to domain services
# =============================================================================


class OmniBarExecutor:
    """
    Executes classified intents against the appropriate domain services.

    This is the action layer that translates extracted entities into
    concrete API calls to create transactions, goals, budgets, or
    query spending data.
    """

    def __init__(self, db_session, user_id: UUID):
        self.db = db_session
        self.user_id = user_id

    async def execute(self, intent_result: IntentResult) -> OmniResponse:
        """Execute an intent and return a response."""
        try:
            handler = {
                OmniIntent.ADD_TRANSACTION: self._add_transaction,
                OmniIntent.ADD_GOAL: self._add_goal,
                OmniIntent.ADD_BUDGET: self._add_budget,
                OmniIntent.UPDATE_GOAL_PROGRESS: self._update_goal_progress,
                OmniIntent.QUERY_SPENDING: self._query_spending,
                OmniIntent.QUERY_GOAL: self._query_goal,
                OmniIntent.QUERY_BUDGET: self._query_budget,
                OmniIntent.QUERY_GENERAL: self._query_general,
                OmniIntent.CHAT: self._handle_chat,
            }.get(intent_result.intent)

            if handler:
                return await handler(intent_result)

            return OmniResponse(
                success=False,
                message="I couldn't understand that. Could you rephrase?",
                intent=intent_result.intent.value,
            )

        except Exception as e:
            logger.error(f"OmniBar execution error: {e}", exc_info=True)
            return OmniResponse(
                success=False,
                message=f"Something went wrong: {str(e)}",
                intent=intent_result.intent.value,
            )

    # ---- Action handlers ----

    async def _add_transaction(self, result: IntentResult) -> OmniResponse:
        """Create a transaction from natural language."""
        from app.services.transaction_service import TransactionService
        from app.schemas.transaction import TransactionCreate, TransactionSource

        entities = result.entities
        amount = entities.get("amount")

        if not amount or amount <= 0:
            return OmniResponse(
                success=False,
                message="I couldn't detect the amount. Could you mention the cost? For example: 'Bought lunch for 250rs'",
                intent=result.intent.value,
                suggestions=[
                    "Spent 250rs on lunch today",
                    "Paid 500 for groceries yesterday",
                ],
            )

        # Build transaction data
        tx_date = entities.get("date", date.today().isoformat())
        if isinstance(tx_date, str):
            try:
                tx_date = date.fromisoformat(tx_date)
            except ValueError:
                tx_date = date.today()

        description = entities.get("description", result.raw_text[:100])
        category = entities.get("category")
        
        # Determine type — check for income keywords
        income_keywords = ["salary", "earned", "income", "received", "got paid", "freelance", "bonus"]
        tx_type = "EXPENSE"
        for kw in income_keywords:
            if kw in result.raw_text.lower():
                tx_type = "INCOME"
                break

        tx_data = TransactionCreate(
            amount=Decimal(str(amount)),
            date=tx_date,
            description=description,
            type=tx_type,
            source=TransactionSource.MANUAL,
            category=category,
        )

        service = TransactionService(self.db)
        created = await service.create_transaction(
            user_id=self.user_id,
            transaction_data=tx_data,
            category=category,
        )

        # Build friendly response
        cat_display = created.category or category or "Uncategorized"
        date_display = tx_date.strftime("%B %d, %Y") if isinstance(tx_date, date) else tx_date
        type_emoji = "💰" if tx_type == "INCOME" else "💸"

        return OmniResponse(
            success=True,
            message=(
                f"{type_emoji} Transaction added!\n\n"
                f"**{description}**\n"
                f"• Amount: ₹{amount:,.2f}\n"
                f"• Category: {cat_display}\n"
                f"• Date: {date_display}\n"
                f"• Type: {tx_type.title()}"
            ),
            intent=result.intent.value,
            data={
                "transaction_id": str(created.id),
                "amount": float(amount),
                "category": cat_display,
                "date": tx_date.isoformat() if isinstance(tx_date, date) else tx_date,
                "type": tx_type,
            },
            confidence=result.confidence,
        )

    async def _add_goal(self, result: IntentResult) -> OmniResponse:
        """Create a financial goal from natural language."""
        from app.services.goal_service import GoalService

        entities = result.entities
        target_amount = entities.get("target_amount")
        name = entities.get("name", "Savings Goal")
        deadline = entities.get("deadline")

        if not target_amount:
            return OmniResponse(
                success=False,
                message="I need a target amount for the goal. For example: 'Save 50000 for a laptop by December'",
                intent=result.intent.value,
                suggestions=[
                    "Save 50000 for a laptop by December",
                    "Create a goal to save 100000 for vacation",
                ],
            )

        deadline_date = None
        if deadline:
            try:
                deadline_date = date.fromisoformat(deadline) if isinstance(deadline, str) else deadline
            except ValueError:
                pass

        service = GoalService(self.db)
        created = await service.create_goal(
            user_id=self.user_id,
            name=name,
            target_amount=Decimal(str(target_amount)),
            deadline=deadline_date,
            category=entities.get("category"),
        )

        deadline_display = deadline_date.strftime("%B %d, %Y") if deadline_date else "No deadline"

        return OmniResponse(
            success=True,
            message=(
                f"🎯 Goal created!\n\n"
                f"**{name}**\n"
                f"• Target: ₹{target_amount:,.2f}\n"
                f"• Deadline: {deadline_display}\n"
                f"• Status: Active"
            ),
            intent=result.intent.value,
            data={
                "goal_id": str(created.id),
                "name": name,
                "target_amount": float(target_amount),
                "deadline": deadline_date.isoformat() if deadline_date else None,
            },
            confidence=result.confidence,
        )

    async def _add_budget(self, result: IntentResult) -> OmniResponse:
        """Create a budget from natural language."""
        from app.services.budget_service import BudgetService

        entities = result.entities
        amount = entities.get("amount")
        category = entities.get("category", "Other")

        if not amount:
            return OmniResponse(
                success=False,
                message="I need a budget amount. For example: 'Set food budget to 5000 for this month'",
                intent=result.intent.value,
                suggestions=[
                    "Set a food budget of 5000 this month",
                    "Budget 10000 for shopping this month",
                ],
            )

        today = date.today()
        period_start = today.replace(day=1)
        if entities.get("period_start"):
            try:
                period_start = date.fromisoformat(entities["period_start"])
            except ValueError:
                pass

        # End of month
        if today.month == 12:
            period_end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        
        if entities.get("period_end"):
            try:
                period_end = date.fromisoformat(entities["period_end"])
            except ValueError:
                pass

        allocations = {category: Decimal(str(amount))}
        budget_name = f"{category} Budget - {period_start.strftime('%b %Y')}"

        service = BudgetService(self.db)
        created = await service.create_budget(
            user_id=self.user_id,
            name=budget_name,
            period_start=period_start,
            period_end=period_end,
            allocations=allocations,
        )

        return OmniResponse(
            success=True,
            message=(
                f"📊 Budget created!\n\n"
                f"**{budget_name}**\n"
                f"• {category}: ₹{amount:,.2f}\n"
                f"• Period: {period_start.strftime('%b %d')} — {period_end.strftime('%b %d, %Y')}"
            ),
            intent=result.intent.value,
            data={
                "budget_id": str(created.id),
                "name": budget_name,
                "category": category,
                "amount": float(amount),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
            confidence=result.confidence,
        )

    async def _update_goal_progress(self, result: IntentResult) -> OmniResponse:
        """Update progress on a financial goal."""
        from app.services.goal_service import GoalService
        from sqlalchemy import select, and_
        from app.models.financial_goal import FinancialGoal

        entities = result.entities
        amount = entities.get("amount")
        goal_name = entities.get("goal_name")

        if not amount:
            return OmniResponse(
                success=False,
                message="How much did you save? For example: 'Saved 5000 towards laptop goal'",
                intent=result.intent.value,
            )

        # Find the goal by name (fuzzy match)
        service = GoalService(self.db)
        goals = await service.list_goals(self.user_id, "ACTIVE")

        target_goal = None
        if goal_name:
            # Simple fuzzy match
            goal_name_lower = goal_name.lower()
            for g in goals:
                if goal_name_lower in g.name.lower() or g.name.lower() in goal_name_lower:
                    target_goal = g
                    break

        if not target_goal and goals:
            # Use the most recent active goal
            target_goal = goals[0]

        if not target_goal:
            return OmniResponse(
                success=False,
                message="I couldn't find an active goal to update. Create one first!",
                intent=result.intent.value,
                suggestions=["Save 50000 for a laptop by December"],
            )

        updated = await service.update_goal_progress(
            goal_id=target_goal.id,
            user_id=self.user_id,
            amount=Decimal(str(amount)),
        )

        progress_pct = (float(updated.current_amount) / float(updated.target_amount)) * 100

        return OmniResponse(
            success=True,
            message=(
                f"✅ Goal progress updated!\n\n"
                f"**{updated.name}**\n"
                f"• Added: ₹{amount:,.2f}\n"
                f"• Progress: ₹{float(updated.current_amount):,.2f} / ₹{float(updated.target_amount):,.2f} ({progress_pct:.1f}%)"
            ),
            intent=result.intent.value,
            data={
                "goal_id": str(updated.id),
                "name": updated.name,
                "current_amount": float(updated.current_amount),
                "target_amount": float(updated.target_amount),
                "progress_percent": round(progress_pct, 1),
            },
            confidence=result.confidence,
        )

    async def _query_spending(self, result: IntentResult) -> OmniResponse:
        """Query spending data."""
        from sqlalchemy import select, func, and_
        from app.models.transaction import Transaction

        entities = result.entities
        category = entities.get("category")
        today = date.today()

        # Determine period
        period_start = entities.get("period_start")
        period_end = entities.get("period_end")

        if period_start:
            try:
                period_start = date.fromisoformat(period_start) if isinstance(period_start, str) else period_start
            except ValueError:
                period_start = today.replace(day=1)
        else:
            period_start = today.replace(day=1)

        if period_end:
            try:
                period_end = date.fromisoformat(period_end) if isinstance(period_end, str) else period_end
            except ValueError:
                period_end = today
        else:
            period_end = today

        # Build query
        conditions = [
            Transaction.user_id == self.user_id,
            Transaction.type == "EXPENSE",
            Transaction.date >= period_start,
            Transaction.date <= period_end,
            Transaction.deleted_at.is_(None),
        ]
        if category:
            conditions.append(Transaction.category == category)

        # Total spending
        total_stmt = select(func.sum(Transaction.amount)).where(and_(*conditions))
        total_result = await self.db.execute(total_stmt)
        total_amount = total_result.scalar() or 0

        # Spending by category
        cat_stmt = (
            select(Transaction.category, func.sum(Transaction.amount).label("total"),
                   func.count(Transaction.id).label("count"))
            .where(and_(*conditions))
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
        )
        cat_result = await self.db.execute(cat_stmt)
        categories = cat_result.all()

        # Build response
        period_label = f"{period_start.strftime('%b %d')} — {period_end.strftime('%b %d, %Y')}"

        if category:
            msg = (
                f"📈 **{category} Spending** ({period_label})\n\n"
                f"Total: **₹{float(total_amount):,.2f}**"
            )
            if categories:
                count = categories[0].count
                msg += f"\n• {count} transaction{'s' if count != 1 else ''}"
        else:
            msg = f"📈 **Spending Summary** ({period_label})\n\nTotal: **₹{float(total_amount):,.2f}**\n"
            if categories:
                msg += "\nBy category:\n"
                for cat_row in categories[:10]:
                    pct = (float(cat_row.total) / float(total_amount) * 100) if total_amount else 0
                    msg += f"• {cat_row.category}: ₹{float(cat_row.total):,.2f} ({pct:.0f}%) — {cat_row.count} txns\n"

        return OmniResponse(
            success=True,
            message=msg.strip(),
            intent=result.intent.value,
            data={
                "total": float(total_amount),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "category_filter": category,
                "breakdown": [
                    {"category": c.category, "total": float(c.total), "count": c.count}
                    for c in categories
                ],
            },
            confidence=result.confidence,
        )

    async def _query_goal(self, result: IntentResult) -> OmniResponse:
        """Query goal progress."""
        from app.services.goal_service import GoalService

        service = GoalService(self.db)
        goals = await service.list_goals(self.user_id, "ACTIVE")

        if not goals:
            return OmniResponse(
                success=True,
                message="You don't have any active goals yet. Would you like to create one?",
                intent=result.intent.value,
                suggestions=[
                    "Save 50000 for a laptop by December",
                    "Create a goal to save 100000 for vacation",
                ],
            )

        msg = "🎯 **Your Goals**\n\n"
        goals_data = []

        for g in goals:
            progress_pct = (float(g.current_amount) / float(g.target_amount)) * 100 if g.target_amount > 0 else 0
            remaining = float(g.target_amount) - float(g.current_amount)
            deadline_str = g.deadline.strftime("%b %d, %Y") if g.deadline else "No deadline"

            # Progress bar
            filled = int(progress_pct / 10)
            bar = "█" * filled + "░" * (10 - filled)

            msg += (
                f"**{g.name}**\n"
                f"[{bar}] {progress_pct:.1f}%\n"
                f"₹{float(g.current_amount):,.2f} / ₹{float(g.target_amount):,.2f} "
                f"(₹{remaining:,.2f} remaining)\n"
                f"📅 {deadline_str}\n\n"
            )

            goals_data.append({
                "id": str(g.id),
                "name": g.name,
                "target": float(g.target_amount),
                "current": float(g.current_amount),
                "progress": round(progress_pct, 1),
                "remaining": remaining,
                "deadline": g.deadline.isoformat() if g.deadline else None,
            })

        return OmniResponse(
            success=True,
            message=msg.strip(),
            intent=result.intent.value,
            data={"goals": goals_data},
            confidence=result.confidence,
        )

    async def _query_budget(self, result: IntentResult) -> OmniResponse:
        """Query budget status."""
        from app.services.budget_service import BudgetService

        service = BudgetService(self.db)
        budgets = await service.list_budgets(self.user_id, active_only=True)

        if not budgets:
            return OmniResponse(
                success=True,
                message="You don't have any active budgets. Would you like to create one?",
                intent=result.intent.value,
                suggestions=[
                    "Set a food budget of 5000 this month",
                    "Budget 10000 for shopping this month",
                ],
            )

        msg = "📊 **Budget Status**\n\n"
        budget_data = []

        for budget in budgets:
            progress = await service.get_budget_progress(self.user_id, budget.id)
            if progress:
                msg += f"**{budget.name}**\n"
                for cat_name, prog in progress.items():
                    status_emoji = "✅" if prog.status == "under" else "⚠️" if prog.status == "warning" else "🔴"
                    msg += (
                        f"{status_emoji} {cat_name}: ₹{float(prog.spent):,.2f} / ₹{float(prog.allocated):,.2f} "
                        f"({prog.percent_used:.0f}%)\n"
                    )
                msg += "\n"
                budget_data.append({
                    "id": str(budget.id),
                    "name": budget.name,
                    "categories": {
                        cat: {
                            "allocated": float(p.allocated),
                            "spent": float(p.spent),
                            "percent_used": p.percent_used,
                            "status": p.status,
                        }
                        for cat, p in progress.items()
                    }
                })

        return OmniResponse(
            success=True,
            message=msg.strip(),
            intent=result.intent.value,
            data={"budgets": budget_data},
            confidence=result.confidence,
        )

    async def _query_general(self, result: IntentResult) -> OmniResponse:
        """Handle general financial queries."""
        from sqlalchemy import select, func, and_
        from app.models.transaction import Transaction

        today = date.today()
        thirty_days_ago = today - timedelta(days=30)

        # Get income
        income_stmt = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == self.user_id,
                Transaction.type == "INCOME",
                Transaction.date >= thirty_days_ago,
                Transaction.date <= today,
                Transaction.deleted_at.is_(None),
            )
        )
        income_result = await self.db.execute(income_stmt)
        total_income = float(income_result.scalar() or 0)

        # Get expenses
        expense_stmt = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == self.user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= thirty_days_ago,
                Transaction.date <= today,
                Transaction.deleted_at.is_(None),
            )
        )
        expense_result = await self.db.execute(expense_stmt)
        total_expenses = float(expense_result.scalar() or 0)

        net_savings = total_income - total_expenses
        savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0

        msg = (
            f"📊 **Financial Overview** (Last 30 Days)\n\n"
            f"• Income: ₹{total_income:,.2f}\n"
            f"• Expenses: ₹{total_expenses:,.2f}\n"
            f"• Net Savings: ₹{net_savings:,.2f}\n"
            f"• Savings Rate: {savings_rate:.1f}%"
        )

        return OmniResponse(
            success=True,
            message=msg,
            intent=result.intent.value,
            data={
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net_savings": net_savings,
                "savings_rate": round(savings_rate, 1),
                "period": "last_30_days",
            },
            confidence=result.confidence,
        )

    async def _handle_chat(self, result: IntentResult) -> OmniResponse:
        """Handle general chat / conversation via AI Brain."""
        from app.services.ai_brain_service import get_ai_brain_service

        try:
            ai_brain = get_ai_brain_service()

            # Build context
            context = await self._build_context()

            ai_response = await ai_brain.chat(
                message=result.raw_text,
                context=context,
            )

            return OmniResponse(
                success=True,
                message=ai_response.response,
                intent=result.intent.value,
                confidence=ai_response.confidence,
            )

        except Exception as e:
            logger.warning(f"AI chat fallback: {e}")
            return OmniResponse(
                success=True,
                message=(
                    "I can help you with:\n\n"
                    "• **Adding transactions** — 'Spent 250rs on lunch yesterday'\n"
                    "• **Creating goals** — 'Save 50000 for a laptop by December'\n"
                    "• **Setting budgets** — 'Set food budget to 5000 this month'\n"
                    "• **Checking spending** — 'How much did I spend on food last month?'\n"
                    "• **Goal progress** — 'How close am I to my goals?'\n"
                    "• **Budget status** — 'Am I over budget?'\n\n"
                    "Try asking me something!"
                ),
                intent=result.intent.value,
                confidence=0.5,
            )

    async def _build_context(self) -> Dict[str, Any]:
        """Build financial context for AI chat."""
        from sqlalchemy import select, func, and_
        from app.models.transaction import Transaction

        today = date.today()
        thirty_days_ago = today - timedelta(days=30)

        # Spending by category
        stmt = (
            select(Transaction.category, func.sum(Transaction.amount).label("total"))
            .where(
                and_(
                    Transaction.user_id == self.user_id,
                    Transaction.type == "EXPENSE",
                    Transaction.date >= thirty_days_ago,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )
        result = await self.db.execute(stmt)
        spending = {row.category: float(row.total) for row in result.all()}

        # Income
        income_stmt = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == self.user_id,
                Transaction.type == "INCOME",
                Transaction.date >= thirty_days_ago,
                Transaction.deleted_at.is_(None),
            )
        )
        income_result = await self.db.execute(income_stmt)
        monthly_income = float(income_result.scalar() or 0)

        return {
            "monthly_income": monthly_income,
            "spending": spending,
            "total_monthly_spending": sum(spending.values()),
        }


# =============================================================================
# Main OmniBar Service (public interface)
# =============================================================================


class OmniBarService:
    """
    Public interface for the OmniBar feature.

    Usage:
        service = OmniBarService(db_session, user_id)
        response = await service.process("Had 2 sandwiches yesterday, cost 250rs")
    """

    def __init__(self, db_session, user_id: UUID):
        self.db = db_session
        self.user_id = user_id
        self.classifier = IntentClassifier()
        self.executor = OmniBarExecutor(db_session, user_id)

    async def process(
        self,
        text: str,
        history: Optional[List[Dict]] = None,
    ) -> OmniResponse:
        """
        Process a natural language command.

        Args:
            text: User's natural language input
            history: Previous conversation messages (for context)

        Returns:
            OmniResponse with the result
        """
        if not text or not text.strip():
            return OmniResponse(
                success=False,
                message="Please type a message or command.",
                intent="none",
            )

        text = text.strip()
        logger.info(f"OmniBar processing: {text[:100]}...")

        # Phase 1: Classify intent
        intent_result = self.classifier.classify(text)

        logger.info(
            f"OmniBar classified intent: {intent_result.intent.value} "
            f"(confidence: {intent_result.confidence:.2f})",
            extra={"entities": intent_result.entities},
        )

        # Phase 2: If confidence is low, try AI-enhanced classification
        if intent_result.confidence < 0.4 and intent_result.intent != OmniIntent.CHAT:
            ai_enhanced = await self._ai_enhance_classification(text, intent_result)
            if ai_enhanced:
                intent_result = ai_enhanced

        # Phase 3: Execute the intent
        response = await self.executor.execute(intent_result)

        return response

    async def _ai_enhance_classification(
        self, text: str, fallback: IntentResult
    ) -> Optional[IntentResult]:
        """Use AI Brain for better intent classification when rules are uncertain."""
        try:
            from app.services.ai_brain_service import get_ai_brain_service

            ai_brain = get_ai_brain_service()

            prompt = f"""Classify this user message for a finance app. Return ONLY a JSON object.

Message: "{text}"

Possible intents:
- add_transaction: User wants to log a new expense or income
- add_goal: User wants to create a savings goal
- add_budget: User wants to set a budget
- update_goal_progress: User saved money towards a goal
- query_spending: User asks about their spending
- query_goal: User asks about goal progress
- query_budget: User asks about budget status
- query_general: User asks general financial questions
- chat: General conversation or financial advice

Return JSON: {{"intent": "...", "confidence": 0.0-1.0, "entities": {{}}}}"""

            result = await ai_brain.query(
                query=prompt, 
                mode=ai_brain.AIBrainMode.CHAT if hasattr(ai_brain, 'AIBrainMode') else "chat",
                use_cache=False,
            )

            # Try to parse AI response as JSON
            response_text = result.response.strip()
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                intent_str = data.get("intent", "chat")
                try:
                    intent = OmniIntent(intent_str)
                except ValueError:
                    return None

                return IntentResult(
                    intent=intent,
                    confidence=data.get("confidence", 0.7),
                    entities={**fallback.entities, **data.get("entities", {})},
                    raw_text=text,
                )

        except Exception as e:
            logger.debug(f"AI enhancement failed, using rule-based result: {e}")

        return None

    async def get_suggestions(self, partial_text: str) -> List[str]:
        """Get autocomplete suggestions for partial input."""
        if not partial_text or len(partial_text) < 2:
            return [
                "Spent ₹__ on __ today",
                "How much did I spend last month?",
                "Save ₹__ for __ by __",
                "Set food budget to ₹__",
                "Am I over budget?",
                "Show my goals progress",
            ]

        text_lower = partial_text.lower()

        suggestions = []

        if any(w in text_lower for w in ["spent", "bought", "had", "paid"]):
            suggestions.extend([
                f"{partial_text} for ₹__",
                f"{partial_text} yesterday",
                f"{partial_text} today",
            ])
        elif any(w in text_lower for w in ["how much", "what"]):
            suggestions.extend([
                "How much did I spend last month?",
                "How much did I spend on food?",
                "How much did I spend this week?",
                "What's my savings rate?",
            ])
        elif any(w in text_lower for w in ["save", "goal"]):
            suggestions.extend([
                "Save 50000 for a laptop by December",
                "Show my goals progress",
                "How close am I to my goals?",
            ])
        elif any(w in text_lower for w in ["budget"]):
            suggestions.extend([
                "Set food budget to 5000 this month",
                "Am I over budget?",
                "Show my budget status",
            ])

        return suggestions[:6]
