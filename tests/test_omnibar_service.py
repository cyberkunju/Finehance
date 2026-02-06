"""Tests for the OmniBar service — Intent classification and entity extraction."""

import pytest
from datetime import date, timedelta

from app.services.omnibar_service import IntentClassifier, OmniIntent


@pytest.fixture
def classifier():
    return IntentClassifier()


# =============================================================================
# Intent Classification Tests
# =============================================================================


class TestIntentClassification:
    """Test intent classification from natural language."""

    def test_add_transaction_spent(self, classifier):
        result = classifier.classify("spent 250rs on lunch today")
        assert result.intent == OmniIntent.ADD_TRANSACTION

    def test_add_transaction_had(self, classifier):
        result = classifier.classify("had 2 sandwiches yesterday 2pm it cost 250rs")
        assert result.intent == OmniIntent.ADD_TRANSACTION

    def test_add_transaction_bought(self, classifier):
        result = classifier.classify("bought groceries for 1500 today")
        assert result.intent == OmniIntent.ADD_TRANSACTION

    def test_add_transaction_paid(self, classifier):
        result = classifier.classify("paid 3000 for electricity bill")
        assert result.intent == OmniIntent.ADD_TRANSACTION

    def test_add_goal(self, classifier):
        result = classifier.classify("save 50000 for a laptop by December")
        assert result.intent == OmniIntent.ADD_GOAL

    def test_add_goal_want(self, classifier):
        result = classifier.classify("I want to save 100000 for a vacation")
        assert result.intent == OmniIntent.ADD_GOAL

    def test_add_budget(self, classifier):
        result = classifier.classify("set food budget to 5000 this month")
        assert result.intent == OmniIntent.ADD_BUDGET

    def test_add_budget_create(self, classifier):
        result = classifier.classify("create a budget of 10000 for shopping")
        assert result.intent == OmniIntent.ADD_BUDGET

    def test_query_spending(self, classifier):
        result = classifier.classify("how much did I spend on food last month")
        assert result.intent == OmniIntent.QUERY_SPENDING

    def test_query_spending_total(self, classifier):
        result = classifier.classify("what was my total spending this week")
        assert result.intent == OmniIntent.QUERY_SPENDING

    def test_query_goal(self, classifier):
        result = classifier.classify("how close am I to my laptop goal")
        assert result.intent == OmniIntent.QUERY_GOAL

    def test_query_goal_progress(self, classifier):
        result = classifier.classify("show my goals progress")
        assert result.intent == OmniIntent.QUERY_GOAL

    def test_query_budget(self, classifier):
        result = classifier.classify("am I over budget on entertainment")
        assert result.intent == OmniIntent.QUERY_BUDGET

    def test_query_general(self, classifier):
        result = classifier.classify("what's my savings rate")
        assert result.intent == OmniIntent.QUERY_GENERAL

    def test_chat_fallback(self, classifier):
        result = classifier.classify("hello how are you")
        assert result.intent == OmniIntent.CHAT

    def test_update_goal_progress(self, classifier):
        result = classifier.classify("saved 5000 towards my laptop goal")
        assert result.intent == OmniIntent.UPDATE_GOAL_PROGRESS


# =============================================================================
# Entity Extraction Tests
# =============================================================================


class TestEntityExtraction:
    """Test entity extraction from natural language."""

    def test_extract_amount_rs(self, classifier):
        result = classifier.classify("spent 250rs on lunch")
        assert result.entities.get("amount") == 250.0

    def test_extract_amount_rupee_symbol(self, classifier):
        result = classifier.classify("spent ₹1500 on groceries")
        assert result.entities.get("amount") == 1500.0

    def test_extract_amount_cost(self, classifier):
        result = classifier.classify("had sandwich it cost 250")
        assert result.entities.get("amount") == 250.0

    def test_extract_amount_dollar(self, classifier):
        result = classifier.classify("spent $50 on coffee")
        assert result.entities.get("amount") == 50.0

    def test_extract_amount_with_comma(self, classifier):
        result = classifier.classify("paid Rs 1,500 for groceries")
        assert result.entities.get("amount") == 1500.0

    def test_extract_date_today(self, classifier):
        result = classifier.classify("spent 250rs on lunch today")
        assert result.entities.get("date") == date.today().isoformat()

    def test_extract_date_yesterday(self, classifier):
        result = classifier.classify("had lunch yesterday cost 250rs")
        expected = (date.today() - timedelta(days=1)).isoformat()
        assert result.entities.get("date") == expected

    def test_extract_time(self, classifier):
        result = classifier.classify("had lunch at 2pm cost 250rs")
        assert result.entities.get("time") == "14:00"

    def test_extract_category_food(self, classifier):
        result = classifier.classify("spent 250 on lunch yesterday")
        assert result.entities.get("category") == "Food & Dining"

    def test_extract_category_transport(self, classifier):
        result = classifier.classify("paid 500 for uber today")
        assert result.entities.get("category") == "Transportation"

    def test_extract_category_groceries(self, classifier):
        result = classifier.classify("bought groceries for 1500")
        assert result.entities.get("category") == "Groceries"

    def test_extract_period_last_month(self, classifier):
        result = classifier.classify("how much did I spend last month")
        assert "period_start" in result.entities
        assert "period_end" in result.entities

    def test_extract_period_this_week(self, classifier):
        result = classifier.classify("total spending this week")
        assert "period_start" in result.entities

    def test_extract_goal_purpose(self, classifier):
        result = classifier.classify("save 50000 for a laptop by December")
        assert result.entities.get("target_amount") == 50000.0
        assert "laptop" in result.entities.get("name", "").lower()

    def test_extract_goal_deadline(self, classifier):
        result = classifier.classify("save 50000 for laptop by December")
        assert result.entities.get("deadline") is not None

    def test_extract_budget_amount(self, classifier):
        result = classifier.classify("set food budget to 5000 this month")
        assert result.entities.get("amount") == 5000.0
        assert result.entities.get("category") is not None

    def test_days_ago(self, classifier):
        result = classifier.classify("spent 300 on snacks 3 days ago")
        expected = (date.today() - timedelta(days=3)).isoformat()
        assert result.entities.get("date") == expected


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and ambiguous inputs."""

    def test_empty_input(self, classifier):
        result = classifier.classify("")
        assert result.intent == OmniIntent.CHAT

    def test_very_short_input(self, classifier):
        result = classifier.classify("hi")
        assert result.intent == OmniIntent.CHAT

    def test_mixed_signals(self, classifier):
        """Input with both spending and goal keywords should pick the stronger one."""
        result = classifier.classify("how much did I spend on food")
        assert result.intent == OmniIntent.QUERY_SPENDING

    def test_no_amount_for_transaction(self, classifier):
        """Transaction without amount should still classify correctly."""
        result = classifier.classify("bought some food today")
        assert result.intent == OmniIntent.ADD_TRANSACTION

    def test_multiple_amounts(self, classifier):
        """Should pick the relevant amount."""
        result = classifier.classify("had 2 sandwiches cost 250rs")
        assert result.entities.get("amount") == 250.0

    def test_unicode_input(self, classifier):
        result = classifier.classify("spent ₹500 on चाय")
        assert result.entities.get("amount") == 500.0

    def test_income_detection(self, classifier):
        result = classifier.classify("got salary 50000")
        assert result.intent == OmniIntent.ADD_TRANSACTION
