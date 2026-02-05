"""Tests for prediction API endpoints."""

import pytest
from datetime import timedelta, date
from decimal import Decimal
from httpx import AsyncClient

from app.models.transaction import Transaction


@pytest.mark.asyncio
class TestPredictionRoutes:
    """Test prediction API endpoints."""

    async def test_get_expense_forecasts_insufficient_data(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test forecasts with insufficient data."""
        user_id = test_user.id

        # Create only a few transactions (less than 30 days)
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test transaction {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(f"/api/predictions/forecast?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        # Should return empty forecasts due to insufficient data
        assert data["total_categories"] == 0
        assert data["forecasts"] == {}

    async def test_get_expense_forecasts_success(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test successful forecast generation."""
        user_id = test_user.id

        # Create sufficient transactions (40 days)
        for i in range(40):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00") + Decimal(str(i % 10)),
                type="EXPENSE",
                category="Groceries",
                description=f"Test transaction {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(f"/api/predictions/forecast?user_id={user_id}&periods=7")

        assert response.status_code == 200
        data = response.json()
        assert data["total_categories"] >= 1
        assert "Groceries" in data["forecasts"]

        forecast = data["forecasts"]["Groceries"]
        assert forecast["category"] == "Groceries"
        assert len(forecast["predictions"]) == 7
        assert len(forecast["confidence_intervals"]) == 7
        assert len(forecast["forecast_dates"]) == 7
        assert "model_params" in forecast
        assert "accuracy_score" in forecast

    async def test_get_category_forecast_success(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test forecast for specific category."""
        user_id = test_user.id

        # Create sufficient transactions with variation
        for i in range(40):
            # Add variation to avoid constant data (ARIMA needs variance)
            amount = Decimal("100.00") + Decimal(str((i % 5) * 2))
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                type="EXPENSE",
                category="Utilities",
                description=f"Utility bill {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(
            f"/api/predictions/forecast/Utilities?user_id={user_id}&periods=14"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "Utilities"
        assert len(data["predictions"]) == 14
        assert len(data["confidence_intervals"]) == 14
        assert len(data["forecast_dates"]) == 14

    async def test_get_category_forecast_insufficient_data(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test forecast with insufficient data for category."""
        user_id = test_user.id

        # Create only a few transactions
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Entertainment",
                description=f"Test {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(
            f"/api/predictions/forecast/Entertainment?user_id={user_id}"
        )

        assert response.status_code == 404
        assert "Insufficient data" in response.json()["detail"]

    async def test_get_category_forecast_custom_parameters(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test forecast with custom parameters."""
        user_id = test_user.id

        # Create sufficient transactions with variation
        for i in range(60):
            # Add variation to avoid constant data (ARIMA needs variance)
            amount = Decimal("75.00") + Decimal(str((i % 7) * 3))
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                type="EXPENSE",
                category="Transport",
                description=f"Transport {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(
            f"/api/predictions/forecast/Transport?user_id={user_id}&periods=21&lookback_days=60"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) == 21

    async def test_get_spending_anomalies_no_data(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test anomaly detection with no data."""
        user_id = test_user.id

        response = await async_client.get(f"/api/predictions/anomalies/Groceries?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_spending_anomalies_with_anomaly(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test anomaly detection with actual anomaly."""
        user_id = test_user.id

        # Create normal spending pattern with MORE variation
        for i in range(40):
            # Add significant variation to normal spending (40-60 range)
            amount = Decimal("50.00") + Decimal(str((i % 5) * 2 - 4))
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                type="EXPENSE",
                category="Groceries",
                description=f"Normal spending {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)

        # Add an anomalous transaction (MUCH higher - 20x normal)
        anomaly_transaction = Transaction(
            user_id=user_id,
            amount=Decimal("1000.00"),  # 20x normal average
            type="EXPENSE",
            category="Groceries",
            description="Anomalous spending",
            date=date.today() - timedelta(days=20),
            source="MANUAL",
        )
        test_db.add(anomaly_transaction)
        await test_db.commit()

        response = await async_client.get(
            f"/api/predictions/anomalies/Groceries?user_id={user_id}&threshold_percent=50"
        )

        assert response.status_code == 200
        data = response.json()
        # Should detect at least one anomaly
        assert len(data) >= 1

        # Check anomaly structure
        if data:
            anomaly = data[0]
            assert "date" in anomaly
            assert anomaly["category"] == "Groceries"
            assert "amount" in anomaly
            assert "expected_amount" in anomaly
            assert "deviation_percent" in anomaly
            assert anomaly["severity"] in ["LOW", "MEDIUM", "HIGH"]

    async def test_forecast_validation_periods(self, async_client: AsyncClient, test_user, test_db):
        """Test forecast with invalid periods parameter."""
        user_id = test_user.id

        # Test periods too high
        response = await async_client.get(
            f"/api/predictions/forecast?user_id={user_id}&periods=100"
        )
        assert response.status_code == 422  # Validation error

        # Test periods too low
        response = await async_client.get(f"/api/predictions/forecast?user_id={user_id}&periods=0")
        assert response.status_code == 422  # Validation error

    async def test_forecast_validation_lookback_days(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test forecast with invalid lookback_days parameter."""
        user_id = test_user.id

        # Test lookback_days too high
        response = await async_client.get(
            f"/api/predictions/forecast?user_id={user_id}&lookback_days=400"
        )
        assert response.status_code == 422  # Validation error

        # Test lookback_days too low
        response = await async_client.get(
            f"/api/predictions/forecast?user_id={user_id}&lookback_days=20"
        )
        assert response.status_code == 422  # Validation error
