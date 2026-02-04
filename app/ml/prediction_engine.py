"""Prediction engine for forecasting future expenses using ARIMA models."""

from datetime import datetime, timedelta, date as date_type
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from uuid import UUID

import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ForecastResult:
    """Result of expense forecast."""
    
    category: str
    predictions: List[Decimal]  # Daily predictions
    confidence_intervals: List[Tuple[Decimal, Decimal]]  # (lower, upper) bounds
    forecast_dates: List[date_type]
    model_params: Dict[str, int]  # (p, d, q) parameters
    accuracy_score: Optional[float] = None


@dataclass
class Anomaly:
    """Detected spending anomaly."""
    
    date: date_type
    category: str
    amount: Decimal
    expected_amount: Decimal
    deviation_percent: float
    severity: str  # LOW, MEDIUM, HIGH


class PredictionEngine:
    """Engine for forecasting future expenses using ARIMA time series models."""
    
    def __init__(self, db: AsyncSession):
        """Initialize prediction engine.
        
        Args:
            db: Database session
        """
        self.db = db
        self.min_data_points = 30  # Minimum days of data required
        self.stationarity_threshold = 0.05  # p-value threshold for ADF test
    
    async def prepare_time_series(
        self,
        user_id: UUID,
        category: str,
        lookback_days: int = 90,
        remove_outliers: bool = True
    ) -> Optional[pd.Series]:
        """Prepare time series data for a specific category.
        
        Aggregates transactions by date, handles missing dates, and performs
        data cleaning including outlier detection.
        
        Args:
            user_id: User ID
            category: Expense category
            lookback_days: Number of days to look back
            remove_outliers: Whether to remove outliers (default True)
            
        Returns:
            Time series as pandas Series with date index, or None if insufficient data
        """
        # Calculate date range
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Query transactions for category
        stmt = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.category == category,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.deleted_at.is_(None)
            )
        ).order_by(Transaction.date)
        
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()
        
        if len(transactions) < self.min_data_points:
            logger.warning(
                "Insufficient data for prediction",
                user_id=str(user_id),
                category=category,
                transaction_count=len(transactions),
                required=self.min_data_points
            )
            return None
        
        # Convert to DataFrame
        data = pd.DataFrame([
            {"date": t.date, "amount": float(t.amount)}
            for t in transactions
        ])
        
        # Aggregate by date (sum multiple transactions on same day)
        daily_data = data.groupby("date")["amount"].sum()
        
        # Create complete date range and fill missing dates with 0
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        time_series = pd.Series(0.0, index=date_range)
        time_series.update(daily_data)
        
        # Handle outliers using IQR method (optional)
        if remove_outliers:
            time_series = self._remove_outliers(time_series)
        
        logger.info(
            "Time series prepared",
            user_id=str(user_id),
            category=category,
            data_points=len(time_series),
            mean=float(time_series.mean()),
            std=float(time_series.std())
        )
        
        return time_series
    
    def _remove_outliers(self, series: pd.Series, iqr_multiplier: float = 1.5) -> pd.Series:
        """Remove outliers using Interquartile Range (IQR) method.
        
        Args:
            series: Time series data
            iqr_multiplier: Multiplier for IQR (1.5 is standard)
            
        Returns:
            Series with outliers replaced by median
        """
        # Only process non-zero values
        non_zero = series[series > 0]
        
        if len(non_zero) < 4:  # Need at least 4 points for quartiles
            return series
        
        q1 = non_zero.quantile(0.25)
        q3 = non_zero.quantile(0.75)
        iqr = q3 - q1
        
        lower_bound = q1 - iqr_multiplier * iqr
        upper_bound = q3 + iqr_multiplier * iqr
        
        # Replace outliers with median
        median = non_zero.median()
        series_clean = series.copy()
        series_clean[(series_clean < lower_bound) | (series_clean > upper_bound)] = median
        
        outlier_count = ((series < lower_bound) | (series > upper_bound)).sum()
        if outlier_count > 0:
            logger.debug(
                "Outliers removed",
                count=outlier_count,
                lower_bound=float(lower_bound),
                upper_bound=float(upper_bound)
            )
        
        return series_clean
    
    def check_stationarity(self, series: pd.Series) -> Tuple[bool, float]:
        """Check if time series is stationary using Augmented Dickey-Fuller test.
        
        Args:
            series: Time series data
            
        Returns:
            Tuple of (is_stationary, p_value)
        """
        # Perform ADF test
        result = adfuller(series, autolag="AIC")
        p_value = result[1]
        is_stationary = p_value < self.stationarity_threshold
        
        logger.debug(
            "Stationarity test",
            is_stationary=is_stationary,
            p_value=float(p_value),
            adf_statistic=float(result[0])
        )
        
        return is_stationary, p_value
    
    def select_arima_parameters(
        self,
        series: pd.Series,
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5
    ) -> Tuple[int, int, int]:
        """Select optimal ARIMA parameters using grid search with AIC.
        
        Args:
            series: Time series data
            max_p: Maximum autoregressive order
            max_d: Maximum differencing order
            max_q: Maximum moving average order
            
        Returns:
            Tuple of (p, d, q) parameters
        """
        # Check stationarity to determine d
        is_stationary, _ = self.check_stationarity(series)
        
        if is_stationary:
            d_values = [0]
        else:
            # Try differencing once or twice
            d_values = [1, 2]
        
        best_aic = np.inf
        best_params = (1, 1, 1)  # Default
        
        # Grid search
        for p in range(max_p + 1):
            for d in d_values:
                for q in range(max_q + 1):
                    if p == 0 and q == 0:
                        continue  # Skip invalid model
                    
                    try:
                        model = ARIMA(series, order=(p, d, q))
                        fitted = model.fit()
                        
                        if fitted.aic < best_aic:
                            best_aic = fitted.aic
                            best_params = (p, d, q)
                    
                    except Exception as e:
                        # Skip parameter combinations that fail
                        logger.debug(
                            "ARIMA parameter combination failed",
                            p=p, d=d, q=q,
                            error=str(e)
                        )
                        continue
        
        logger.info(
            "ARIMA parameters selected",
            p=best_params[0],
            d=best_params[1],
            q=best_params[2],
            aic=float(best_aic)
        )
        
        return best_params

    
    async def forecast_expenses(
        self,
        user_id: UUID,
        category: str,
        periods: int = 30,
        lookback_days: int = 90
    ) -> Optional[ForecastResult]:
        """Forecast future expenses for a specific category.
        
        Args:
            user_id: User ID
            category: Expense category
            periods: Number of days to forecast
            lookback_days: Number of historical days to use
            
        Returns:
            ForecastResult with predictions and confidence intervals, or None if insufficient data
        """
        # Prepare time series data
        series = await self.prepare_time_series(user_id, category, lookback_days)
        
        if series is None:
            return None
        
        # Select ARIMA parameters
        p, d, q = self.select_arima_parameters(series)
        
        try:
            # Fit ARIMA model
            model = ARIMA(series, order=(p, d, q))
            fitted_model = model.fit()
            
            # Generate forecast
            forecast = fitted_model.forecast(steps=periods)
            forecast_conf_int = fitted_model.get_forecast(steps=periods).conf_int()
            
            # Convert to lists of Decimals
            predictions = [Decimal(str(max(0, val))) for val in forecast]
            
            # Confidence intervals (lower, upper)
            confidence_intervals = [
                (
                    Decimal(str(max(0, forecast_conf_int.iloc[i, 0]))),
                    Decimal(str(max(0, forecast_conf_int.iloc[i, 1])))
                )
                for i in range(len(forecast_conf_int))
            ]
            
            # Generate forecast dates
            start_date = datetime.utcnow().date() + timedelta(days=1)
            forecast_dates = [start_date + timedelta(days=i) for i in range(periods)]
            
            # Calculate accuracy score (in-sample)
            in_sample_pred = fitted_model.fittedvalues
            actual = series[-len(in_sample_pred):]
            mape = np.mean(np.abs((actual - in_sample_pred) / (actual + 1))) * 100
            accuracy = max(0, 100 - mape)
            
            result = ForecastResult(
                category=category,
                predictions=predictions,
                confidence_intervals=confidence_intervals,
                forecast_dates=forecast_dates,
                model_params={"p": p, "d": d, "q": q},
                accuracy_score=float(accuracy)
            )
            
            logger.info(
                "Forecast generated",
                user_id=str(user_id),
                category=category,
                periods=periods,
                accuracy=float(accuracy),
                mean_prediction=float(np.mean([float(p) for p in predictions]))
            )
            
            return result
        
        except Exception as e:
            logger.error(
                "Forecast generation failed",
                user_id=str(user_id),
                category=category,
                error=str(e)
            )
            return None
    
    async def forecast_all_categories(
        self,
        user_id: UUID,
        periods: int = 30,
        lookback_days: int = 90
    ) -> Dict[str, ForecastResult]:
        """Forecast expenses for all categories with sufficient data.
        
        Args:
            user_id: User ID
            periods: Number of days to forecast
            lookback_days: Number of historical days to use
            
        Returns:
            Dictionary mapping category to ForecastResult
        """
        # Get all expense categories for user
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        stmt = select(Transaction.category).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.deleted_at.is_(None)
            )
        ).distinct()
        
        result = await self.db.execute(stmt)
        categories = [row[0] for row in result.all()]
        
        # Generate forecasts for each category
        forecasts = {}
        for category in categories:
            forecast = await self.forecast_expenses(
                user_id=user_id,
                category=category,
                periods=periods,
                lookback_days=lookback_days
            )
            
            if forecast is not None:
                forecasts[category] = forecast
        
        logger.info(
            "All categories forecasted",
            user_id=str(user_id),
            total_categories=len(categories),
            successful_forecasts=len(forecasts)
        )
        
        return forecasts
    
    async def detect_anomalies(
        self,
        user_id: UUID,
        category: str,
        lookback_days: int = 90,
        threshold_percent: float = 50.0
    ) -> List[Anomaly]:
        """Detect unusual spending patterns in a category.
        
        Args:
            user_id: User ID
            category: Expense category
            lookback_days: Number of days to analyze
            threshold_percent: Deviation threshold for anomaly detection
            
        Returns:
            List of detected anomalies
        """
        # Prepare time series WITHOUT removing outliers (we want to detect them!)
        series = await self.prepare_time_series(
            user_id, category, lookback_days, remove_outliers=False
        )
        
        if series is None:
            return []
        
        # Calculate rolling statistics
        window = min(7, len(series) // 3)  # 7-day window or 1/3 of data
        rolling_mean = series.rolling(window=window, center=True).mean()
        rolling_std = series.rolling(window=window, center=True).std()
        
        # Detect anomalies
        anomalies = []
        for date, amount in series.items():
            if amount == 0:
                continue  # Skip zero spending days
            
            expected = rolling_mean[date]
            std = rolling_std[date]
            
            if pd.isna(expected) or pd.isna(std) or std == 0:
                continue
            
            # Calculate deviation
            deviation = abs(amount - expected)
            deviation_percent = (deviation / expected) * 100
            
            if deviation_percent > threshold_percent:
                # Determine severity
                if deviation_percent > 100:
                    severity = "HIGH"
                elif deviation_percent > 75:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"
                
                anomalies.append(Anomaly(
                    date=date.date(),
                    category=category,
                    amount=Decimal(str(amount)),
                    expected_amount=Decimal(str(expected)),
                    deviation_percent=float(deviation_percent),
                    severity=severity
                ))
        
        logger.info(
            "Anomalies detected",
            user_id=str(user_id),
            category=category,
            anomaly_count=len(anomalies)
        )
        
        return anomalies
    
    async def calculate_prediction_error(
        self,
        user_id: UUID,
        category: str,
        forecast_result: ForecastResult,
        actual_days: int = 30
    ) -> float:
        """Calculate prediction error by comparing forecast to actual spending.
        
        Args:
            user_id: User ID
            category: Expense category
            forecast_result: Previous forecast result
            actual_days: Number of days to compare
            
        Returns:
            Mean Absolute Percentage Error (MAPE)
        """
        # Get actual transactions for the forecast period
        start_date = forecast_result.forecast_dates[0]
        end_date = start_date + timedelta(days=actual_days - 1)
        
        stmt = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.category == category,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.deleted_at.is_(None)
            )
        )
        
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()
        
        # Aggregate actual spending by date
        actual_data = {}
        for t in transactions:
            if t.date not in actual_data:
                actual_data[t.date] = Decimal(0)
            actual_data[t.date] += t.amount
        
        # Calculate MAPE
        errors = []
        for i, forecast_date in enumerate(forecast_result.forecast_dates[:actual_days]):
            predicted = float(forecast_result.predictions[i])
            actual = float(actual_data.get(forecast_date, Decimal(0)))
            
            # Avoid division by zero
            if actual > 0:
                error = abs(actual - predicted) / actual
                errors.append(error)
        
        if not errors:
            return 0.0
        
        mape = np.mean(errors) * 100
        
        logger.info(
            "Prediction error calculated",
            user_id=str(user_id),
            category=category,
            mape=float(mape),
            samples=len(errors)
        )
        
        return float(mape)
    
    async def should_recalibrate(
        self,
        user_id: UUID,
        category: str,
        forecast_result: ForecastResult,
        error_threshold: float = 20.0
    ) -> bool:
        """Determine if model should be recalibrated based on prediction error.
        
        Args:
            user_id: User ID
            category: Expense category
            forecast_result: Previous forecast result
            error_threshold: MAPE threshold for recalibration (default 20%)
            
        Returns:
            True if recalibration is needed
        """
        # Calculate prediction error
        mape = await self.calculate_prediction_error(
            user_id=user_id,
            category=category,
            forecast_result=forecast_result
        )
        
        needs_recalibration = mape > error_threshold
        
        if needs_recalibration:
            logger.warning(
                "Model recalibration needed",
                user_id=str(user_id),
                category=category,
                mape=float(mape),
                threshold=error_threshold
            )
        
        return needs_recalibration
    
    async def recalibrate_model(
        self,
        user_id: UUID,
        category: str,
        periods: int = 30
    ) -> Optional[ForecastResult]:
        """Retrain model with latest data when prediction error exceeds threshold.
        
        Args:
            user_id: User ID
            category: Expense category
            periods: Number of days to forecast
            
        Returns:
            New ForecastResult with recalibrated model
        """
        logger.info(
            "Recalibrating model",
            user_id=str(user_id),
            category=category
        )
        
        # Simply generate a new forecast with latest data
        # This will use the most recent transactions and retrain the model
        return await self.forecast_expenses(
            user_id=user_id,
            category=category,
            periods=periods,
            lookback_days=90  # Use 90 days of recent data
        )
