"""Tests for database models."""

from sqlalchemy import inspect

from app.models import (
    Base,
    User,
    Transaction,
    Budget,
    FinancialGoal,
    MLModel,
    Connection,
)


class TestModelDefinitions:
    """Test that all models are properly defined."""

    def test_all_models_inherit_from_base(self):
        """All models should inherit from Base."""
        models = [User, Transaction, Budget, FinancialGoal, MLModel, Connection]
        for model in models:
            assert issubclass(model, Base)

    def test_all_models_have_tablename(self):
        """All models should have __tablename__ defined."""
        models = [User, Transaction, Budget, FinancialGoal, MLModel, Connection]
        expected_names = [
            "users",
            "transactions",
            "budgets",
            "financial_goals",
            "ml_models",
            "connections",
        ]
        for model, expected_name in zip(models, expected_names):
            assert model.__tablename__ == expected_name

    def test_all_models_have_primary_key(self):
        """All models should have a primary key column named 'id'."""
        models = [User, Transaction, Budget, FinancialGoal, MLModel, Connection]
        for model in models:
            mapper = inspect(model)
            pk_columns = [col.name for col in mapper.primary_key]
            assert "id" in pk_columns
            assert len(pk_columns) == 1


class TestUserModel:
    """Test User model definition."""

    def test_user_required_columns(self):
        """User should have all required columns."""
        mapper = inspect(User)
        column_names = [col.name for col in mapper.columns]

        required_columns = [
            "id",
            "email",
            "password_hash",
            "first_name",
            "last_name",
            "created_at",
            "updated_at",
        ]

        for col in required_columns:
            assert col in column_names

    def test_user_email_unique(self):
        """User email should have unique constraint."""
        mapper = inspect(User)
        email_col = mapper.columns["email"]
        assert email_col.unique or any(
            "email" in [c.name for c in constraint.columns]
            for constraint in mapper.tables[0].constraints
            if hasattr(constraint, "columns")
        )

    def test_user_relationships(self):
        """User should have relationships to other models."""
        mapper = inspect(User)
        relationship_names = [rel.key for rel in mapper.relationships]

        expected_relationships = [
            "transactions",
            "budgets",
            "financial_goals",
            "ml_models",
            "connections",
        ]

        for rel in expected_relationships:
            assert rel in relationship_names


class TestTransactionModel:
    """Test Transaction model definition."""

    def test_transaction_required_columns(self):
        """Transaction should have all required columns."""
        mapper = inspect(Transaction)
        column_names = [col.name for col in mapper.columns]

        required_columns = [
            "id",
            "user_id",
            "amount",
            "date",
            "description",
            "category",
            "type",
            "source",
            "confidence_score",
            "connection_id",
            "created_at",
            "updated_at",
            "deleted_at",
        ]

        for col in required_columns:
            assert col in column_names

    def test_transaction_foreign_keys(self):
        """Transaction should have foreign keys to User and Connection."""
        mapper = inspect(Transaction)
        fk_columns = {fk.parent.name: fk.column.table.name for fk in mapper.tables[0].foreign_keys}

        assert "user_id" in fk_columns
        assert fk_columns["user_id"] == "users"
        assert "connection_id" in fk_columns
        assert fk_columns["connection_id"] == "connections"

    def test_transaction_check_constraints(self):
        """Transaction should have check constraints for type and source."""
        mapper = inspect(Transaction)
        table = mapper.tables[0]

        constraint_names = [c.name for c in table.constraints]

        assert "check_transaction_type" in constraint_names
        assert "check_transaction_source" in constraint_names
        assert "check_amount_positive" in constraint_names
        assert "check_confidence_score_range" in constraint_names


class TestBudgetModel:
    """Test Budget model definition."""

    def test_budget_required_columns(self):
        """Budget should have all required columns."""
        mapper = inspect(Budget)
        column_names = [col.name for col in mapper.columns]

        required_columns = [
            "id",
            "user_id",
            "name",
            "period_start",
            "period_end",
            "allocations",
            "created_at",
            "updated_at",
        ]

        for col in required_columns:
            assert col in column_names

    def test_budget_allocations_is_jsonb(self):
        """Budget allocations should be JSONB type."""
        mapper = inspect(Budget)
        allocations_col = mapper.columns["allocations"]
        assert "JSONB" in str(allocations_col.type)


class TestFinancialGoalModel:
    """Test FinancialGoal model definition."""

    def test_financial_goal_required_columns(self):
        """FinancialGoal should have all required columns."""
        mapper = inspect(FinancialGoal)
        column_names = [col.name for col in mapper.columns]

        required_columns = [
            "id",
            "user_id",
            "name",
            "target_amount",
            "current_amount",
            "deadline",
            "category",
            "status",
            "created_at",
            "updated_at",
        ]

        for col in required_columns:
            assert col in column_names

    def test_financial_goal_check_constraints(self):
        """FinancialGoal should have check constraints."""
        mapper = inspect(FinancialGoal)
        table = mapper.tables[0]

        constraint_names = [c.name for c in table.constraints]

        assert "check_goal_status" in constraint_names
        assert "check_target_amount_positive" in constraint_names
        assert "check_current_amount_non_negative" in constraint_names


class TestMLModelModel:
    """Test MLModel model definition."""

    def test_ml_model_required_columns(self):
        """MLModel should have all required columns."""
        mapper = inspect(MLModel)
        column_names = [col.name for col in mapper.columns]

        required_columns = [
            "id",
            "model_type",
            "user_id",
            "version",
            "accuracy",
            "precision",
            "recall",
            "trained_at",
            "model_path",
            "is_active",
        ]

        for col in required_columns:
            assert col in column_names

    def test_ml_model_check_constraints(self):
        """MLModel should have check constraints for metrics."""
        mapper = inspect(MLModel)
        table = mapper.tables[0]

        constraint_names = [c.name for c in table.constraints]

        assert "check_model_type" in constraint_names
        assert "check_accuracy_range" in constraint_names
        assert "check_precision_range" in constraint_names
        assert "check_recall_range" in constraint_names


class TestConnectionModel:
    """Test Connection model definition."""

    def test_connection_required_columns(self):
        """Connection should have all required columns."""
        mapper = inspect(Connection)
        column_names = [col.name for col in mapper.columns]

        required_columns = [
            "id",
            "user_id",
            "institution_id",
            "institution_name",
            "access_token",
            "last_sync",
            "status",
            "created_at",
        ]

        for col in required_columns:
            assert col in column_names

    def test_connection_check_constraints(self):
        """Connection should have check constraint for status."""
        mapper = inspect(Connection)
        table = mapper.tables[0]

        constraint_names = [c.name for c in table.constraints]

        assert "check_connection_status" in constraint_names


class TestModelIndexes:
    """Test that models have appropriate indexes."""

    def test_transaction_indexes(self):
        """Transaction should have indexes for common queries."""
        mapper = inspect(Transaction)
        table = mapper.tables[0]
        index_names = [idx.name for idx in table.indexes]

        # Check for composite indexes
        assert "idx_transactions_user_date" in index_names
        assert "idx_transactions_user_category" in index_names
        assert "idx_transactions_user_type" in index_names

    def test_budget_indexes(self):
        """Budget should have indexes for period queries."""
        mapper = inspect(Budget)
        table = mapper.tables[0]
        index_names = [idx.name for idx in table.indexes]

        assert "idx_budgets_user_period" in index_names

    def test_financial_goal_indexes(self):
        """FinancialGoal should have indexes for status and deadline."""
        mapper = inspect(FinancialGoal)
        table = mapper.tables[0]
        index_names = [idx.name for idx in table.indexes]

        assert "idx_financial_goals_user_status" in index_names
        assert "idx_financial_goals_user_deadline" in index_names

    def test_ml_model_indexes(self):
        """MLModel should have indexes for type and active status."""
        mapper = inspect(MLModel)
        table = mapper.tables[0]
        index_names = [idx.name for idx in table.indexes]

        assert "idx_ml_models_type_active" in index_names
        assert "idx_ml_models_user_type" in index_names
        assert "idx_ml_models_user_type_active" in index_names

    def test_connection_indexes(self):
        """Connection should have indexes for user and status."""
        mapper = inspect(Connection)
        table = mapper.tables[0]
        index_names = [idx.name for idx in table.indexes]

        assert "idx_connections_user_status" in index_names
        assert "idx_connections_user_institution" in index_names
