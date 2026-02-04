"""ML Model Management API endpoints."""

import os
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.ml.categorization_engine import CategorizationEngine
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Request/Response Models
class ModelInfoResponse(BaseModel):
    """Information about a trained model."""
    model_type: str
    exists: bool
    accuracy: Optional[float] = None
    training_samples: Optional[int] = None
    trained_at: Optional[str] = None
    unique_categories: Optional[int] = None


class GlobalModelStatus(BaseModel):
    """Status of the global categorization model."""
    loaded: bool
    path: str
    accuracy: Optional[float] = None


class UserModelStatus(BaseModel):
    """Status of a user-specific model."""
    has_model: bool
    correction_count: int
    corrections_needed: int
    accuracy: Optional[float] = None
    can_train: bool


class CategorizeRequest(BaseModel):
    """Request to categorize a transaction."""
    description: str = Field(..., min_length=1, max_length=500)
    amount: Optional[float] = None
    user_id: Optional[UUID] = None
    use_llm_fallback: bool = Field(True, description="Use AI Brain for low-confidence predictions")


class CategorizeResponse(BaseModel):
    """Categorization result."""
    category: str
    confidence: float
    model_type: str
    llm_enhanced: bool = False


class CorrectionRequest(BaseModel):
    """Request to submit a categorization correction."""
    user_id: UUID
    description: str = Field(..., min_length=1)
    correct_category: str = Field(..., min_length=1)


class TrainModelRequest(BaseModel):
    """Request to train a user model."""
    user_id: UUID
    force: bool = Field(False, description="Force training even with insufficient data")


class BatchCategorizeRequest(BaseModel):
    """Request to categorize multiple transactions."""
    transactions: list[dict] = Field(..., description="List of {description, amount} dicts")
    user_id: Optional[UUID] = None


# Engine singleton
_categorization_engine: Optional[CategorizationEngine] = None


def get_categorization_engine() -> CategorizationEngine:
    """Get or create categorization engine."""
    global _categorization_engine
    if _categorization_engine is None:
        _categorization_engine = CategorizationEngine(model_dir=settings.model_storage_path)
    return _categorization_engine


# Endpoints
@router.get("/status")
async def get_ml_status(
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> dict:
    """Get overall ML system status."""
    global_loaded = engine.global_model is not None
    global_path = os.path.join(engine.model_dir, "global_categorization_model.pkl")
    global_exists = os.path.exists(global_path)
    
    return {
        "global_model": {
            "loaded": global_loaded,
            "exists": global_exists,
            "path": global_path,
        },
        "user_models_cached": len(engine.user_models),
        "model_directory": engine.model_dir,
        "min_corrections_for_training": engine.min_corrections_for_training,
    }


@router.get("/models/global", response_model=GlobalModelStatus)
async def get_global_model_status(
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> GlobalModelStatus:
    """Get global categorization model status."""
    model_path = os.path.join(engine.model_dir, "global_categorization_model.pkl")
    metrics_path = os.path.join(engine.model_dir, "global_categorization_metrics.pkl")
    
    accuracy = None
    if os.path.exists(metrics_path):
        import joblib
        try:
            metrics = joblib.load(metrics_path)
            accuracy = metrics.get("accuracy")
        except Exception:
            pass
    
    return GlobalModelStatus(
        loaded=engine.global_model is not None,
        path=model_path,
        accuracy=accuracy,
    )


@router.get("/models/user/{user_id}", response_model=UserModelStatus)
async def get_user_model_status(
    user_id: UUID,
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> UserModelStatus:
    """Get user-specific model status."""
    has_model = engine.has_user_model(str(user_id))
    correction_count = engine.get_correction_count(str(user_id))
    accuracy = engine.get_model_accuracy(str(user_id)) if has_model else None
    
    return UserModelStatus(
        has_model=has_model,
        correction_count=correction_count,
        corrections_needed=max(0, engine.min_corrections_for_training - correction_count),
        accuracy=accuracy,
        can_train=correction_count >= engine.min_corrections_for_training,
    )


@router.post("/categorize", response_model=CategorizeResponse)
async def categorize_transaction(
    request: CategorizeRequest,
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> CategorizeResponse:
    """
    Categorize a single transaction.
    
    Uses the global model or user-specific model if available.
    Optionally falls back to AI Brain for low-confidence predictions.
    """
    from decimal import Decimal
    
    try:
        # Get prediction from ML model
        prediction = engine.categorize(
            description=request.description,
            amount=Decimal(str(request.amount)) if request.amount else None,
            user_id=str(request.user_id) if request.user_id else None,
        )
        
        llm_enhanced = False
        
        # If confidence is low and LLM fallback is enabled, try AI Brain
        if request.use_llm_fallback and prediction.confidence < 0.7:
            try:
                from app.services.ai_brain_service import get_ai_brain_service
                ai_brain = get_ai_brain_service()
                
                # Use async await
                result = await ai_brain.parse_transaction(request.description)
                
                if result.parsed_data and result.confidence > prediction.confidence:
                    llm_category = result.parsed_data.get("category")
                    if llm_category:
                        prediction.category = llm_category
                        prediction.confidence = result.confidence
                        llm_enhanced = True
            except Exception as e:
                logger.debug("LLM fallback failed", error=str(e))
        
        return CategorizeResponse(
            category=prediction.category,
            confidence=prediction.confidence,
            model_type=prediction.model_type,
            llm_enhanced=llm_enhanced,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Categorization failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Categorization failed: {str(e)}")


@router.post("/categorize/batch")
async def batch_categorize(
    request: BatchCategorizeRequest,
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> dict:
    """Categorize multiple transactions at once."""
    from decimal import Decimal
    
    results = []
    errors = []
    
    for i, txn in enumerate(request.transactions):
        try:
            description = txn.get("description", "")
            amount = txn.get("amount")
            
            if not description:
                errors.append({"index": i, "error": "Missing description"})
                continue
            
            prediction = engine.categorize(
                description=description,
                amount=Decimal(str(amount)) if amount else None,
                user_id=str(request.user_id) if request.user_id else None,
            )
            
            results.append({
                "index": i,
                "description": description,
                "category": prediction.category,
                "confidence": prediction.confidence,
                "model_type": prediction.model_type,
            })
            
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    
    return {
        "results": results,
        "errors": errors,
        "total": len(request.transactions),
        "successful": len(results),
        "failed": len(errors),
    }


@router.post("/corrections")
async def submit_correction(
    request: CorrectionRequest,
    background_tasks: BackgroundTasks,
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> dict:
    """
    Submit a categorization correction.
    
    The system learns from corrections and will train a user-specific
    model once enough corrections are collected.
    """
    try:
        model_trained = engine.learn_from_correction(
            user_id=str(request.user_id),
            description=request.description,
            correct_category=request.correct_category,
        )
        
        correction_count = engine.get_correction_count(str(request.user_id))
        
        return {
            "success": True,
            "model_trained": model_trained,
            "correction_count": correction_count,
            "corrections_needed": max(0, engine.min_corrections_for_training - correction_count),
        }
        
    except Exception as e:
        logger.error("Correction submission failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to submit correction: {str(e)}")


@router.post("/models/user/{user_id}/train")
async def train_user_model(
    user_id: UUID,
    request: TrainModelRequest,
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> dict:
    """
    Manually trigger user model training.
    
    Requires sufficient corrections unless force=True.
    """
    correction_count = engine.get_correction_count(str(user_id))
    
    if not request.force and correction_count < engine.min_corrections_for_training:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient corrections: {correction_count}/{engine.min_corrections_for_training}"
        )
    
    try:
        corrections = engine._load_user_corrections(str(user_id))
        success = engine._train_user_model(str(user_id), corrections)
        
        if success:
            accuracy = engine.get_model_accuracy(str(user_id))
            return {
                "success": True,
                "accuracy": accuracy,
                "training_samples": len(corrections),
            }
        else:
            raise HTTPException(status_code=500, detail="Training failed")
            
    except Exception as e:
        logger.error("User model training failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.get("/categories")
async def get_categories() -> dict:
    """Get list of available categories."""
    categories_path = os.path.join(settings.model_storage_path, "categories.json")
    
    # Default categories
    default_categories = [
        "Food & Dining",
        "Shopping & Retail",
        "Transportation",
        "Entertainment",
        "Utilities",
        "Healthcare",
        "Travel",
        "Subscriptions",
        "Income",
        "Transfer",
        "Other Expenses",
    ]
    
    if os.path.exists(categories_path):
        try:
            import json
            with open(categories_path, 'r') as f:
                categories = json.load(f)
            return {"categories": categories, "source": "file"}
        except Exception:
            pass
    
    return {"categories": default_categories, "source": "default"}


@router.delete("/models/user/{user_id}")
async def delete_user_model(
    user_id: UUID,
    engine: CategorizationEngine = Depends(get_categorization_engine)
) -> dict:
    """Delete a user's personalized model and corrections."""
    import os
    
    model_path = os.path.join(engine.model_dir, f"user_{user_id}_categorization_model.pkl")
    metrics_path = os.path.join(engine.model_dir, f"user_{user_id}_categorization_metrics.pkl")
    corrections_path = os.path.join(engine.model_dir, f"user_{user_id}_corrections.json")
    
    deleted = []
    
    for path, name in [(model_path, "model"), (metrics_path, "metrics"), (corrections_path, "corrections")]:
        if os.path.exists(path):
            os.remove(path)
            deleted.append(name)
    
    # Clear from cache
    if str(user_id) in engine.user_models:
        del engine.user_models[str(user_id)]
    
    return {
        "success": True,
        "deleted": deleted,
    }
