"""Unit tests for Categorization Engine."""

import pytest
import os
import glob
from decimal import Decimal

from app.ml.categorization_engine import CategorizationEngine


@pytest.fixture
def categorization_engine() -> CategorizationEngine:
    """Create categorization engine instance."""
    engine = CategorizationEngine()

    # Clean up any test user files before test
    test_files = glob.glob(os.path.join(engine.model_dir, "user_test_*"))
    for file in test_files:
        try:
            os.remove(file)
        except Exception:
            pass

    yield engine

    # Clean up any test user files after test
    test_files = glob.glob(os.path.join(engine.model_dir, "user_test_*"))
    for file in test_files:
        try:
            os.remove(file)
        except Exception:
            pass


class TestCategorizationEngine:
    """Tests for categorization engine."""

    def test_categorize_with_global_model(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization using global model."""
        # Test with known merchant
        result = categorization_engine.categorize(description="Whole Foods Market", user_id=None)

        assert result.category == "Groceries"
        assert result.confidence > 0.5
        assert result.model_type == "GLOBAL"

    def test_categorize_dining(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization of dining transactions."""
        result = categorization_engine.categorize(description="Starbucks Coffee")

        assert result.category == "Dining"
        assert result.confidence > 0.0
        assert result.model_type == "GLOBAL"

    def test_categorize_transportation(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization of transportation transactions."""
        result = categorization_engine.categorize(description="Shell Gas Station")

        assert result.category == "Transportation"
        assert result.confidence > 0.0
        assert result.model_type == "GLOBAL"

    def test_categorize_entertainment(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization of entertainment transactions."""
        result = categorization_engine.categorize(description="Netflix Subscription")

        assert result.category == "Entertainment"
        assert result.confidence > 0.0
        assert result.model_type == "GLOBAL"

    def test_categorize_salary(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization of salary transactions."""
        result = categorization_engine.categorize(description="Payroll Deposit")

        assert result.category == "Salary"
        assert result.confidence > 0.0
        assert result.model_type == "GLOBAL"

    def test_categorize_with_amount(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization with amount parameter."""
        result = categorization_engine.categorize(
            description="Amazon Purchase", amount=Decimal("50.00")
        )

        assert result.category == "Shopping"
        assert result.confidence > 0.0
        assert result.model_type == "GLOBAL"

    def test_categorize_case_insensitive(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test that categorization is case-insensitive."""
        result1 = categorization_engine.categorize("WHOLE FOODS MARKET")
        result2 = categorization_engine.categorize("whole foods market")
        result3 = categorization_engine.categorize("Whole Foods Market")

        assert result1.category == result2.category == result3.category
        assert result1.category == "Groceries"

    def test_categorize_with_extra_text(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization with transaction IDs and dates."""
        result = categorization_engine.categorize(
            description="Whole Foods Market #12345 01/15/2024"
        )

        assert result.category == "Groceries"
        assert result.confidence > 0.0

    def test_should_use_global_model_no_user_id(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test that global model is used when no user_id provided."""
        assert categorization_engine.should_use_global_model(None) is True

    def test_should_use_global_model_new_user(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test that global model is used for new users."""
        # New user with no personalized model
        assert categorization_engine.should_use_global_model("new_user_123") is True

    def test_get_model_accuracy_global(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test getting global model accuracy."""
        accuracy = categorization_engine.get_model_accuracy("new_user_123")

        # Should return global model accuracy (>80%)
        assert accuracy > 0.80

    def test_learn_from_correction(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test recording user correction."""
        # Should not raise an error
        categorization_engine.learn_from_correction(
            user_id="test_user", description="Unknown Merchant", correct_category="Shopping"
        )

    def test_categorize_multiple_transactions(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorizing multiple transactions."""
        test_cases = [
            ("Walmart Grocery", "Groceries"),
            ("McDonald's", "Dining"),
            ("Uber Ride", "Transportation"),
            ("Electric Bill", "Utilities"),
            ("Movie Theater", "Entertainment"),
            ("CVS Pharmacy", "Healthcare"),
            ("Amazon", "Shopping"),
            ("Hotel Booking", "Travel"),
            ("Tuition Payment", "Education"),
            ("Rent Payment", "Housing"),
        ]

        for description, expected_category in test_cases:
            result = categorization_engine.categorize(description)
            assert result.category == expected_category, (
                f"Expected {expected_category} for '{description}', got {result.category}"
            )
            assert result.confidence > 0.0
            assert result.model_type == "GLOBAL"

    def test_confidence_score_range(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test that confidence scores are between 0 and 1."""
        descriptions = ["Whole Foods Market", "Starbucks", "Shell Gas", "Netflix", "Payroll"]

        for desc in descriptions:
            result = categorization_engine.categorize(desc)
            assert 0.0 <= result.confidence <= 1.0, (
                f"Confidence {result.confidence} out of range for '{desc}'"
            )

    def test_categorize_ambiguous_description(
        self,
        categorization_engine: CategorizationEngine,
    ):
        """Test categorization with ambiguous description."""
        # "Target" could be groceries or shopping
        result = categorization_engine.categorize("Target")

        # Should return a category (either is acceptable)
        assert result.category in ["Groceries", "Shopping"]
        assert result.confidence >= 0.0

    def test_learn_from_correction_stores_correction(self, categorization_engine):
        """Test that corrections are stored."""
        user_id = "test_user_123"

        # Add a correction
        result = categorization_engine.learn_from_correction(
            user_id=user_id, description="Starbucks coffee", correct_category="Dining"
        )

        # Should not train yet (need 50 corrections)
        assert result is False

        # Check correction count
        count = categorization_engine.get_correction_count(user_id)
        assert count == 1

        # Should not have user model yet
        assert not categorization_engine.has_user_model(user_id)

    def test_learn_from_correction_trains_model_after_threshold(self, categorization_engine):
        """Test that model is trained after sufficient corrections."""
        user_id = "test_user_456"

        # Add 50 corrections with diverse categories
        categories = ["Dining", "Transportation", "Entertainment", "Shopping", "Utilities"]
        for i in range(50):
            category = categories[i % len(categories)]
            result = categorization_engine.learn_from_correction(
                user_id=user_id,
                description=f"Transaction {i} for {category}",
                correct_category=category,
            )

        # Last correction should trigger training
        assert result is True

        # Should have user model now
        assert categorization_engine.has_user_model(user_id)

        # Should use user model for this user
        assert not categorization_engine.should_use_global_model(user_id)

    def test_learn_from_correction_uses_user_model(self, categorization_engine):
        """Test that user model is used after training."""
        user_id = "test_user_789"

        # Add 50 corrections with specific pattern
        # All "coffee" transactions should be "Dining"
        for i in range(50):
            if i % 2 == 0:
                categorization_engine.learn_from_correction(
                    user_id=user_id, description=f"Coffee shop {i}", correct_category="Dining"
                )
            else:
                categorization_engine.learn_from_correction(
                    user_id=user_id, description=f"Uber ride {i}", correct_category="Transportation"
                )

        # Categorize a new coffee transaction
        result = categorization_engine.categorize(
            description="Morning coffee at cafe", user_id=user_id
        )

        # Should use user-specific model
        assert result.model_type == "USER_SPECIFIC"
        assert result.category == "Dining"

    def test_get_correction_count(self, categorization_engine):
        """Test getting correction count for a user."""
        user_id = "test_user_count"

        # Initially zero
        assert categorization_engine.get_correction_count(user_id) == 0

        # Add corrections
        for i in range(5):
            categorization_engine.learn_from_correction(
                user_id=user_id, description=f"Transaction {i}", correct_category="Dining"
            )

        # Should have 5 corrections
        assert categorization_engine.get_correction_count(user_id) == 5

    def test_has_user_model(self, categorization_engine):
        """Test checking if user has a personalized model."""
        user_id = "test_user_model_check"

        # Initially no model
        assert not categorization_engine.has_user_model(user_id)

        # Add enough corrections to train model
        for i in range(50):
            category = "Dining" if i % 2 == 0 else "Transportation"
            categorization_engine.learn_from_correction(
                user_id=user_id, description=f"Transaction {i}", correct_category=category
            )

        # Should have model now
        assert categorization_engine.has_user_model(user_id)

    def test_learn_from_correction_insufficient_category_diversity(self, categorization_engine):
        """Test that training fails with insufficient category diversity."""
        user_id = "test_user_single_category"

        # Add 50 corrections but all same category
        for i in range(50):
            result = categorization_engine.learn_from_correction(
                user_id=user_id, description=f"Transaction {i}", correct_category="Dining"
            )

        # Training should fail due to insufficient diversity
        assert result is False
        assert not categorization_engine.has_user_model(user_id)

    def test_user_model_accuracy_tracking(self, categorization_engine):
        """Test that user model accuracy is tracked."""
        user_id = "test_user_accuracy"

        # Add diverse corrections
        categories = ["Dining", "Transportation", "Entertainment"]
        for i in range(60):
            category = categories[i % len(categories)]
            categorization_engine.learn_from_correction(
                user_id=user_id,
                description=f"Transaction {i} for {category}",
                correct_category=category,
            )

        # Get accuracy
        accuracy = categorization_engine.get_model_accuracy(user_id)

        # Should have reasonable accuracy
        assert 0.0 <= accuracy <= 1.0
        assert accuracy > 0.5  # Should be better than random

    def test_learn_from_correction_persistence(self, categorization_engine):
        """Test that corrections persist across engine instances."""
        user_id = "test_user_persistence"

        # Add corrections
        for i in range(10):
            categorization_engine.learn_from_correction(
                user_id=user_id, description=f"Transaction {i}", correct_category="Dining"
            )

        # Create new engine instance
        new_engine = CategorizationEngine(model_dir=categorization_engine.model_dir)

        # Should still have corrections
        assert new_engine.get_correction_count(user_id) == 10
