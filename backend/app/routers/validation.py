# Validation router - Run validations via API

import os
import math
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import pandas as pd
import numpy as np

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.project import Project
from ..models.ml_model import MLModel
from ..models.dataset import Dataset
from ..models.requirement import Requirement
from ..models.validation import Validation, ValidationResult, ValidationStatus
from ..models.audit_log import AuditLog, AuditAction, ResourceType
from ..services.model_loader import UniversalModelLoader
from ..validators.fairness_validator import FairnessValidator
from ..validators.explainability_engine import ExplainabilityEngine
from ..validators.privacy_validator import PrivacyValidator
from ..middleware.logging_config import get_logger

logger = get_logger("routers.validation")
router = APIRouter(prefix="/validate", tags=["validation"])


def _json_safe(obj: Any) -> Any:
    """Recursively sanitize objects for strict JSON serialization.

    Converts non-finite floats (NaN/Inf) to None so Starlette can serialize.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_json_safe(v) for v in obj)
    return obj


# Request/Response models
class FairnessValidationRequest(BaseModel):
    model_id: UUID
    dataset_id: UUID
    sensitive_feature: str
    target_column: Optional[str] = None  # Optional - if not provided, uses predictions
    thresholds: Optional[Dict[str, float]] = None
    selected_metrics: Optional[List[str]] = None


class FairnessFromPredictionsRequest(BaseModel):
    """
    Run fairness analysis using a dataset that already contains model predictions.
    No separate ML model file is needed.
    """
    dataset_id: UUID
    sensitive_feature: str
    prediction_column: str        # column in the dataset holding predicted labels / scores
    actual_column: Optional[str] = None   # ground-truth column (improves metric set when provided)
    thresholds: Optional[Dict[str, float]] = None
    selected_metrics: Optional[List[str]] = None


class TransparencyValidationRequest(BaseModel):
    model_id: UUID
    dataset_id: UUID
    target_column: Optional[str] = None  # Optional
    sample_size: int = 100  # Number of samples for SHAP


class PrivacyValidationRequest(BaseModel):
    dataset_id: UUID
    k_anonymity_k: Optional[int] = 5
    l_diversity_l: Optional[int] = 2
    quasi_identifiers: Optional[List[str]] = None
    sensitive_attribute: Optional[str] = None
    selected_checks: Optional[List[str]] = None
    # Differential Privacy config
    dp_target_epsilon: Optional[float] = 1.0
    dp_apply_noise: Optional[bool] = False


class ValidationStatusResponse(BaseModel):
    id: UUID
    status: str
    progress: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]


class FairnessResultResponse(BaseModel):
    validation_id: UUID
    status: str
    overall_passed: bool
    metrics: Dict[str, Any]
    group_metrics: Dict[str, Any]
    visualizations: Optional[Dict[str, str]]  # base64 encoded images


class TransparencyResultResponse(BaseModel):
    validation_id: UUID
    status: str
    global_importance: Dict[str, float]
    model_card: Dict[str, Any]
    visualizations: Optional[Dict[str, str]]


class PrivacyResultResponse(BaseModel):
    validation_id: UUID
    status: str
    overall_passed: bool
    pii_detected: List[Dict[str, Any]]
    k_anonymity: Optional[Dict[str, Any]]
    l_diversity: Optional[Dict[str, Any]]
    recommendations: List[str]


async def verify_access(
    db: AsyncSession,
    current_user: User,
    project_id: UUID
) -> bool:
    """Verify user has access to the project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        return False
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        return False
    
    return True


@router.post("/fairness", response_model=FairnessResultResponse)
async def run_fairness_validation(
    request: FairnessValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run fairness validation on a model+dataset combination.
    
    This endpoint:
    1. Loads the uploaded model
    2. Loads the test dataset
    3. Runs predictions
    4. Calculates fairness metrics using Fairlearn
    5. Returns pass/fail results with visualizations
    """
    # Get model
    result = await db.execute(
        select(MLModel).where(MLModel.id == request.model_id)
    )
    model_record = result.scalar_one_or_none()
    
    if not model_record:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Verify access
    if not await verify_access(db, current_user, model_record.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get dataset
    result = await db.execute(
        select(Dataset).where(Dataset.id == request.dataset_id)
    )
    dataset_record = result.scalar_one_or_none()
    
    if not dataset_record:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not model_record.file_path or not os.path.exists(model_record.file_path):
        raise HTTPException(
            status_code=400,
            detail="Model file is missing on disk. Please re-upload the model before running validation."
        )

    if not dataset_record.file_path or not os.path.exists(dataset_record.file_path):
        raise HTTPException(
            status_code=400,
            detail="Dataset file is missing on disk. Please re-upload the dataset before running validation."
        )
    
    # Validate columns exist
    if request.sensitive_feature not in dataset_record.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Sensitive feature '{request.sensitive_feature}' not found in dataset"
        )
    
    if request.target_column not in dataset_record.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Target column '{request.target_column}' not found in dataset"
        )
    
    # Create validation record
    validation = Validation(
        model_id=model_record.id,
        dataset_id=dataset_record.id,
        status=ValidationStatus.RUNNING,
        progress=0,
        started_at=datetime.now(timezone.utc)
    )
    db.add(validation)
    await db.commit()
    await db.refresh(validation)
    
    logger.info(
        "Fairness validation started: id=%s model=%s dataset=%s",
        validation.id, model_record.name, dataset_record.name,
    )
    
    try:
        # Load model
        model = UniversalModelLoader.load(model_record.file_path)
        
        # Load dataset
        df = pd.read_csv(dataset_record.file_path)
        
        # Prepare data
        X = df.drop(columns=[request.target_column])
        y_true = df[request.target_column].values
        sensitive = df[request.sensitive_feature].values
        
        # Handle non-numeric features (simple label encoding)
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = pd.factorize(X[col])[0]
        
        # Get predictions
        y_pred = model.predict(X.values)
        
        # Run fairness validation
        thresholds = request.thresholds or {
            'demographic_parity_ratio': 0.8,
            'equalized_odds_ratio': 0.8,
            'disparate_impact_ratio': 0.8
        }
        
        validator = FairnessValidator(
            y_true=y_true,
            y_pred=y_pred,
            sensitive_features=sensitive
        )
        
        report = validator.validate_all(
            thresholds=thresholds,
            selected_metrics=request.selected_metrics,
        )
        
        # Update validation status
        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Create audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.VALIDATION_RUN,
            resource_type=ResourceType.VALIDATION,
            resource_id=validation.id,
            details={
                "validation_type": "fairness",
                "model_name": model_record.name,
                "dataset_name": dataset_record.name,
                "passed": report.overall_passed
            }
        )
        db.add(audit)
        await db.commit()
        
        logger.info("Fairness validation completed: id=%s passed=%s", validation.id, report.overall_passed)
        
        # Format response
        metrics = {}
        for m in report.metrics:
            metrics[m.metric_name] = {
                "value": m.overall_value,
                "threshold": m.threshold,
                "passed": m.passed,
                "by_group": m.by_group
            }
        
        return FairnessResultResponse(
            validation_id=validation.id,
            status="completed",
            overall_passed=report.overall_passed,
            metrics=metrics,
            group_metrics={
                "groups": report.groups,
                "sample_sizes": report.sample_sizes
            },
            visualizations=report.visualizations
        )
        
    except Exception as e:
        # Update validation status on error with rollback recovery
        try:
            await db.rollback()
            validation.status = ValidationStatus.FAILED
            validation.error_message = str(e)[:2000]
            validation.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as db_err:
            logger.error("Failed to persist fairness error state: %s", db_err)
        
        logger.error("Fairness validation failed: id=%s error=%s", validation.id, e)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)[:500]}")


@router.post("/fairness-from-predictions", response_model=FairnessResultResponse)
async def run_fairness_from_predictions(
    request: FairnessFromPredictionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run fairness validation using predictions that are already stored inside the dataset.

    Use this when you have a CSV that contains both the sensitive feature column and a
    column with the model's predicted labels – without needing to upload the model file
    itself.  If you also provide ``actual_column`` (ground truth), threshold-based metrics
    such as Equalized Odds can be computed; otherwise only group-parity metrics are used.

    Note: Explainability / SHAP analysis is not available in this mode because the model
    file is not present.
    """
    # Load dataset record
    result = await db.execute(select(Dataset).where(Dataset.id == request.dataset_id))
    dataset_record = result.scalar_one_or_none()
    if not dataset_record:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Verify project access
    if not await verify_access(db, current_user, dataset_record.project_id):
        raise HTTPException(status_code=403, detail="Access denied")

    if not dataset_record.file_path or not os.path.exists(dataset_record.file_path):
        raise HTTPException(status_code=400, detail="Dataset file is missing on disk. Please re-upload.")

    cols = dataset_record.columns or []
    if request.sensitive_feature not in cols:
        raise HTTPException(status_code=400, detail=f"Sensitive feature '{request.sensitive_feature}' not found in dataset")
    if request.prediction_column not in cols:
        raise HTTPException(status_code=400, detail=f"Prediction column '{request.prediction_column}' not found in dataset")
    if request.actual_column and request.actual_column not in cols:
        raise HTTPException(status_code=400, detail=f"Actual column '{request.actual_column}' not found in dataset")

    # Create validation record (no model_id)
    validation = Validation(
        dataset_id=dataset_record.id,
        status=ValidationStatus.RUNNING,
        progress=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(validation)
    await db.commit()
    await db.refresh(validation)

    logger.info(
        "Fairness-from-predictions validation started: id=%s dataset=%s pred_col=%s",
        validation.id, dataset_record.name, request.prediction_column,
    )

    try:
        df = pd.read_csv(dataset_record.file_path)

        y_pred = df[request.prediction_column].values
        y_true = df[request.actual_column].values if request.actual_column else y_pred
        sensitive = df[request.sensitive_feature].values

        thresholds = request.thresholds or {
            "demographic_parity_ratio": 0.8,
            "equalized_odds_ratio": 0.8,
            "disparate_impact_ratio": 0.8,
        }

        validator = FairnessValidator(y_true=y_true, y_pred=y_pred, sensitive_features=sensitive)
        report = validator.validate_all(thresholds=thresholds, selected_metrics=request.selected_metrics)

        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.VALIDATION_RUN,
            resource_type=ResourceType.VALIDATION,
            resource_id=validation.id,
            details={
                "validation_type": "fairness_from_predictions",
                "dataset_name": dataset_record.name,
                "prediction_column": request.prediction_column,
                "passed": report.overall_passed,
            },
        )
        db.add(audit)
        await db.commit()

        logger.info("Fairness-from-predictions completed: id=%s passed=%s", validation.id, report.overall_passed)

        metrics = {}
        for m in report.metrics:
            metrics[m.metric_name] = {
                "value": m.overall_value,
                "threshold": m.threshold,
                "passed": m.passed,
                "by_group": m.by_group,
            }

        return FairnessResultResponse(
            validation_id=validation.id,
            status="completed",
            overall_passed=report.overall_passed,
            metrics=metrics,
            group_metrics={"groups": report.groups, "sample_sizes": report.sample_sizes},
            visualizations=report.visualizations,
        )

    except Exception as e:
        try:
            await db.rollback()
            validation.status = ValidationStatus.FAILED
            validation.error_message = str(e)[:2000]
            validation.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as db_err:
            logger.error("Failed to persist fairness-from-predictions error state: %s", db_err)
        logger.error("Fairness-from-predictions failed: id=%s error=%s", validation.id, e)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)[:500]}")


@router.post("/transparency", response_model=TransparencyResultResponse)
async def run_transparency_validation(
    request: TransparencyValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run transparency validation (SHAP explanations) on a model.
    
    Returns:
    - Global feature importance
    - Model card
    - SHAP visualizations
    """
    # Get model
    result = await db.execute(
        select(MLModel).where(MLModel.id == request.model_id)
    )
    model_record = result.scalar_one_or_none()
    
    if not model_record:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if not await verify_access(db, current_user, model_record.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get dataset
    result = await db.execute(
        select(Dataset).where(Dataset.id == request.dataset_id)
    )
    dataset_record = result.scalar_one_or_none()
    
    if not dataset_record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Create validation record
    validation = Validation(
        model_id=model_record.id,
        dataset_id=dataset_record.id,
        status=ValidationStatus.RUNNING,
        progress=0,
        started_at=datetime.now(timezone.utc)
    )
    db.add(validation)
    await db.commit()
    await db.refresh(validation)
    
    try:
        # Load model
        model = UniversalModelLoader.load(model_record.file_path)
        
        # Load dataset
        df = pd.read_csv(dataset_record.file_path)
        
        # Prepare data
        X = df.drop(columns=[request.target_column])
        y = df[request.target_column].values
        feature_names = X.columns.tolist()
        
        # Handle non-numeric features
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = pd.factorize(X[col])[0]
        
        X_values = X.values
        
        # Sample for performance
        sample_size = min(request.sample_size, len(X_values))
        indices = np.random.choice(len(X_values), sample_size, replace=False)
        X_sample = X_values[indices]
        
        # Initialize explainability engine
        engine = ExplainabilityEngine(
            model=model,
            X_train=X_sample,
            feature_names=feature_names
        )
        
        # Get global explanations
        global_exp = engine.explain_global_shap(X_sample)
        
        # Generate model card
        model_card = engine.generate_model_card(
            model_name=model_record.name,
            model_version=model_record.version,
            intended_use="Classification",
            training_data=f"{dataset_record.name} ({dataset_record.row_count} samples)",
            evaluation_data=f"{sample_size} samples",
            performance_metrics={}
        )
        
        # Update validation status
        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.VALIDATION_RUN,
            resource_type=ResourceType.VALIDATION,
            resource_id=validation.id,
            details={
                "validation_type": "transparency",
                "model_name": model_record.name,
                "sample_size": sample_size
            }
        )
        db.add(audit)
        await db.commit()
        
        # Format importance dict
        importance_dict = {
            fi.feature_name: fi.importance
            for fi in global_exp.feature_importances
        }
        
        return TransparencyResultResponse(
            validation_id=validation.id,
            status="completed",
            global_importance=importance_dict,
            model_card=model_card.to_dict(),
            visualizations=global_exp.visualizations
        )
        
    except Exception as e:
        try:
            await db.rollback()
            validation.status = ValidationStatus.FAILED
            validation.error_message = str(e)[:2000]
            validation.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as db_err:
            logger.error("Failed to persist transparency error state: %s", db_err)
        
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)[:500]}")


@router.post("/privacy", response_model=PrivacyResultResponse)
async def run_privacy_validation(
    request: PrivacyValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run privacy validation on a dataset.
    
    Checks:
    - PII detection (emails, phones, SSNs, etc.)
    - k-Anonymity (if quasi-identifiers provided)
    - l-Diversity (if sensitive attribute provided)
    """
    # Get dataset
    result = await db.execute(
        select(Dataset).where(Dataset.id == request.dataset_id)
    )
    dataset_record = result.scalar_one_or_none()
    
    if not dataset_record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    if not await verify_access(db, current_user, dataset_record.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Create validation record (no model for privacy checks)
    validation = Validation(
        dataset_id=dataset_record.id,
        status=ValidationStatus.RUNNING,
        progress=0,
        started_at=datetime.now(timezone.utc)
    )
    db.add(validation)
    await db.commit()
    await db.refresh(validation)
    
    try:
        # Load dataset
        df = pd.read_csv(dataset_record.file_path)
        
        # Initialize privacy validator
        validator = PrivacyValidator(df)
        
        # Build requirements
        selected_checks = set(c.lower() for c in (request.selected_checks or ['pii_detection', 'k_anonymity', 'l_diversity']))
        requirements: Dict[str, Any] = {}

        if 'pii_detection' in selected_checks:
            requirements['pii_detection'] = True

        if 'k_anonymity' in selected_checks:
            if not request.quasi_identifiers:
                raise HTTPException(
                    status_code=400,
                    detail="k-anonymity selected but quasi_identifiers were not provided"
                )
            # Validate columns exist
            invalid = set(request.quasi_identifiers) - set(df.columns)
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quasi-identifier columns not found: {invalid}"
                )
            requirements['k_anonymity'] = {
                'k': request.k_anonymity_k,
                'quasi_identifiers': request.quasi_identifiers
            }

        if 'l_diversity' in selected_checks:
            if not request.quasi_identifiers:
                raise HTTPException(
                    status_code=400,
                    detail="l-diversity selected but quasi_identifiers were not provided"
                )
            if not request.sensitive_attribute:
                raise HTTPException(
                    status_code=400,
                    detail="l-diversity selected but sensitive_attribute was not provided"
                )
            if request.sensitive_attribute not in df.columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sensitive attribute '{request.sensitive_attribute}' not found"
                )
            requirements['l_diversity'] = {
                'l': request.l_diversity_l,
                'quasi_identifiers': request.quasi_identifiers,
                'sensitive_attribute': request.sensitive_attribute
            }

        if not requirements:
            raise HTTPException(status_code=400, detail="No privacy checks selected")
        
        # Run validation
        report = validator.validate(requirements)
        
        # Update validation status
        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.VALIDATION_RUN,
            resource_type=ResourceType.VALIDATION,
            resource_id=validation.id,
            details={
                "validation_type": "privacy",
                "dataset_name": dataset_record.name,
                "passed": report.overall_passed
            }
        )
        db.add(audit)
        await db.commit()
        
        # Format response
        pii_list = [r.to_dict() for r in report.pii_results if r.is_pii]
        
        return PrivacyResultResponse(
            validation_id=validation.id,
            status="completed",
            overall_passed=report.overall_passed,
            pii_detected=pii_list,
            k_anonymity=report.k_anonymity.to_dict() if report.k_anonymity else None,
            l_diversity=report.l_diversity.to_dict() if report.l_diversity else None,
            recommendations=report.recommendations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        try:
            await db.rollback()
            validation.status = ValidationStatus.FAILED
            validation.error_message = str(e)[:2000]
            validation.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as db_err:
            logger.error("Failed to persist privacy error state: %s", db_err)
        
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)[:500]}")


@router.get("/{validation_id}", response_model=ValidationStatusResponse)
async def get_validation_status(
    validation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the status of a validation run."""
    result = await db.execute(
        select(Validation).where(Validation.id == validation_id)
    )
    validation = result.scalar_one_or_none()
    
    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")
    
    return ValidationStatusResponse(
        id=validation.id,
        status=validation.status.value,
        progress=validation.progress,
        started_at=validation.started_at,
        completed_at=validation.completed_at,
        error_message=validation.error_message
    )


@router.get("/history/{project_id}")
async def get_validation_history(
    project_id: UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get validation history for a project, including suite information."""
    if not await verify_access(db, current_user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    from ..models.validation_suite import ValidationSuite
    from sqlalchemy.orm import selectinload
    
    # Get validation suites for models in this project
    result = await db.execute(
        select(ValidationSuite)
        .join(MLModel, ValidationSuite.model_id == MLModel.id)
        .options(
            selectinload(ValidationSuite.model),
            selectinload(ValidationSuite.dataset)
        )
        .where(MLModel.project_id == project_id)
        .order_by(ValidationSuite.started_at.desc())
        .limit(limit)
    )
    suites = result.scalars().all()
    
    history = []
    for suite in suites:
        # Count results for each validation
        fairness_results = []
        transparency_results = []
        privacy_results = []
        
        if suite.fairness_validation_id:
            results_query = await db.execute(
                select(ValidationResult).where(ValidationResult.validation_id == suite.fairness_validation_id)
            )
            fairness_results = results_query.scalars().all()
        
        if suite.transparency_validation_id:
            results_query = await db.execute(
                select(ValidationResult).where(ValidationResult.validation_id == suite.transparency_validation_id)
            )
            transparency_results = results_query.scalars().all()
            
        if suite.privacy_validation_id:
            results_query = await db.execute(
                select(ValidationResult).where(ValidationResult.validation_id == suite.privacy_validation_id)
            )
            privacy_results = results_query.scalars().all()
        
        history.append({
            "suite_id": str(suite.id),
            "model_name": suite.model.name if suite.model else "Unknown",
            "dataset_name": suite.dataset.name if suite.dataset else "Unknown",
            "status": suite.status,
            "overall_passed": suite.overall_passed,
            "started_at": suite.started_at.isoformat() if suite.started_at else None,
            "completed_at": suite.completed_at.isoformat() if suite.completed_at else None,
            "error_message": suite.error_message,
            "validations": {
                "fairness": {
                    "completed": suite.fairness_validation_id is not None,
                    "metrics_count": len(fairness_results),
                    "passed_count": sum(1 for r in fairness_results if r.passed),
                    "metrics": {
                        r.metric_name: {"value": r.metric_value, "threshold": r.threshold, "passed": r.passed}
                        for r in fairness_results
                        if r.metric_name and r.metric_value is not None
                    },
                },
                "transparency": {
                    "completed": suite.transparency_validation_id is not None,
                    "metrics_count": len(transparency_results),
                    "passed_count": sum(1 for r in transparency_results if r.passed),
                    "metrics": {
                        r.metric_name: {"value": r.metric_value, "threshold": r.threshold, "passed": r.passed}
                        for r in transparency_results
                        if r.metric_name and r.metric_value is not None
                    },
                },
                "privacy": {
                    "completed": suite.privacy_validation_id is not None,
                    "metrics_count": len(privacy_results),
                    "passed_count": sum(1 for r in privacy_results if r.passed),
                    "metrics": {
                        r.metric_name: {"value": r.metric_value, "threshold": r.threshold, "passed": r.passed}
                        for r in privacy_results
                        if r.metric_name and r.metric_value is not None
                    },
                }
            }
        })
    
    return history
class AllValidationsRequest(BaseModel):
    """Request to run all 4 validations in sequence."""
    model_id: UUID
    dataset_id: UUID
    fairness_config: Dict[str, Any]
    transparency_config: Dict[str, Any]
    privacy_config: Dict[str, Any]
    # Optional subset – if None/empty, every validator runs (backward-compatible)
    selected_validations: Optional[List[str]] = None
    # Optional requirement IDs to link validations to specific requirements
    requirement_ids: Optional[List[UUID]] = None


class ValidationSuiteResponse(BaseModel):
    """Response for validation suite creation."""
    suite_id: UUID
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Response for task status check."""
    task_id: str
    state: str
    progress: int
    current_step: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


@router.post("/all", response_model=ValidationSuiteResponse)
async def run_all_validations(
    request: AllValidationsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run all 4 ethical validations in sequence as a background task.
    
    This endpoint:
    1. Creates a ValidationSuite record
    2. Queues a Celery task to run all validations
    3. Returns immediately with task_id for status tracking
    
    The validations run in this order:
    - Fairness validation
    - Transparency/Explainability validation
    - Privacy validation
    - Accountability (tracked via MLflow)
    """
    from ..models.validation_suite import ValidationSuite
    from ..tasks.validation_tasks import run_all_validations_task
    
    # Verify model access
    result = await db.execute(
        select(MLModel).where(MLModel.id == request.model_id)
    )
    model_record = result.scalar_one_or_none()
    
    if not model_record:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if not await verify_access(db, current_user, model_record.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Verify dataset access
    result = await db.execute(
        select(Dataset).where(Dataset.id == request.dataset_id)
    )
    dataset_record = result.scalar_one_or_none()
    
    if not dataset_record:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Create validation suite
    suite = ValidationSuite(
        model_id=request.model_id,
        dataset_id=request.dataset_id,
        status="pending",
        created_by_id=current_user.id,
        started_at=datetime.now(timezone.utc)
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    
    # Queue background task
    task = run_all_validations_task.delay(
        suite_id=str(suite.id),
        model_id=str(request.model_id),
        dataset_id=str(request.dataset_id),
        fairness_config=request.fairness_config,
        transparency_config=request.transparency_config,
        privacy_config=request.privacy_config,
        user_id=str(current_user.id),
        selected_validations=request.selected_validations or [],
        requirement_ids=[str(rid) for rid in request.requirement_ids] if request.requirement_ids else []
    )
    
    # Update suite with task ID
    suite.celery_task_id = task.id
    suite.status = "running"
    await db.commit()
    
    # Create audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.VALIDATION_RUN,
        resource_type=ResourceType.VALIDATION,
        resource_id=suite.id,
        details={
            "validation_type": "all",
            "model_name": model_record.name,
            "dataset_name": dataset_record.name,
            "task_id": task.id
        }
    )
    db.add(audit)
    await db.commit()
    
    return ValidationSuiteResponse(
        suite_id=suite.id,
        task_id=task.id,
        status="queued",
        message="Validation suite queued. Use task_id to check status."
    )


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of a background validation task.
    
    Use this endpoint to poll for task progress and results.
    
    States:
    - PENDING: Task is queued but not started
    - PROGRESS: Task is running (check progress field)
    - SUCCESS: Task completed successfully (check result field)
    - FAILURE: Task failed (check error field)
    """
    from celery.result import AsyncResult
    from ..celery_app import celery_app
    
    task = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "state": task.state,
        "progress": 0,
        "current_step": None,
        "result": None,
        "error": None
    }
    
    if task.state == "PENDING":
        response["progress"] = 0
        response["current_step"] = "Queued"
    elif task.state == "PROGRESS":
        info = task.info or {}
        response["progress"] = info.get("progress", 0)
        response["current_step"] = info.get("step", "Processing")
    elif task.state == "SUCCESS":
        response["progress"] = 100
        response["current_step"] = "Completed"
        response["result"] = task.result
    elif task.state == "FAILURE":
        response["progress"] = 0
        response["current_step"] = "Failed"
        response["error"] = str(task.info)
    
    return TaskStatusResponse(**response)


@router.get("/suite/{suite_id}/results")
async def get_suite_results(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregate results for a validation suite.
    
    Returns all validation results in a single response:
    - Fairness validation results
    - Transparency validation results
    - Privacy validation results
    - Overall pass/fail status
    - MLflow run IDs for accountability
    """
    from ..models.validation_suite import ValidationSuite
    from sqlalchemy.orm import selectinload
    
    # Get validation suite with eager loading of relationships
    result = await db.execute(
        select(ValidationSuite)
        .options(selectinload(ValidationSuite.model))  # Eager load the model relationship
        .where(ValidationSuite.id == suite_id)
    )
    suite = result.scalar_one_or_none()
    
    if not suite:
        raise HTTPException(status_code=404, detail="Validation suite not found")
    
    # Verify access - Get the model to check project_id
    result = await db.execute(
        select(MLModel).where(MLModel.id == suite.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if not await verify_access(db, current_user, model.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Build response
    response = {
        "suite_id": str(suite.id),
        "status": suite.status,
        "overall_passed": suite.overall_passed,
        "started_at": suite.started_at.isoformat() if suite.started_at else None,
        "completed_at": suite.completed_at.isoformat() if suite.completed_at else None,
        "error_message": suite.error_message,
        "validations": {}
    }
    
    # Get fairness validation
    if suite.fairness_validation_id:
        result = await db.execute(
            select(Validation).where(Validation.id == suite.fairness_validation_id)
        )
        fairness_val = result.scalar_one_or_none()
        if fairness_val:
            # Get detailed results
            results_query = await db.execute(
                select(ValidationResult).where(ValidationResult.validation_id == fairness_val.id)
            )
            validation_results = results_query.scalars().all()
            
            response["validations"]["fairness"] = {
                "validation_id": str(fairness_val.id),
                "status": fairness_val.status if isinstance(fairness_val.status, str) else fairness_val.status.value,
                "progress": fairness_val.progress,
                "mlflow_run_id": fairness_val.mlflow_run_id,
                "completed_at": fairness_val.completed_at.isoformat() if fairness_val.completed_at else None,
                "results": [
                    {
                        "metric_name": r.metric_name,
                        "metric_value": r.metric_value,
                        "threshold": r.threshold,
                        "passed": r.passed,
                        "details": r.details
                    }
                    for r in validation_results
                ]
            }
    
    # Get transparency validation
    if suite.transparency_validation_id:
        result = await db.execute(
            select(Validation).where(Validation.id == suite.transparency_validation_id)
        )
        transparency_val = result.scalar_one_or_none()
        if transparency_val:
            # The Celery task stores full transparency data in its result dict.
            # Retrieve the task result to get global_importance, lime, fidelity, etc.
            transparency_data: Dict[str, Any] = {
                "validation_id": str(transparency_val.id),
                "status": transparency_val.status if isinstance(transparency_val.status, str) else transparency_val.status.value,
                "progress": transparency_val.progress,
                "mlflow_run_id": transparency_val.mlflow_run_id,
                "completed_at": transparency_val.completed_at.isoformat() if transparency_val.completed_at else None,
            }

            # Try to recover the rich transparency payload from the Celery result
            if suite.celery_task_id:
                try:
                    from celery.result import AsyncResult
                    from ..celery_app import celery_app as _celery
                    task_result = AsyncResult(suite.celery_task_id, app=_celery)
                    if task_result.state == "SUCCESS" and task_result.result:
                        t_vals = task_result.result.get("validations", {}).get("transparency", {})
                        if t_vals:
                            transparency_data["global_importance"] = t_vals.get("global_importance")
                            transparency_data["model_card"] = t_vals.get("model_card")
                            transparency_data["sample_predictions"] = t_vals.get("sample_predictions")
                            transparency_data["lime_explanations"] = t_vals.get("lime_explanations")
                            transparency_data["explanation_fidelity"] = t_vals.get("explanation_fidelity")
                            transparency_data["warning"] = t_vals.get("warning")
                except Exception:
                    pass  # Non-fatal – basic data still returned

            response["validations"]["transparency"] = transparency_data
    
    # Get privacy validation
    if suite.privacy_validation_id:
        result = await db.execute(
            select(Validation).where(Validation.id == suite.privacy_validation_id)
        )
        privacy_val = result.scalar_one_or_none()
        if privacy_val:
            response["validations"]["privacy"] = {
                "validation_id": str(privacy_val.id),
                "status": privacy_val.status if isinstance(privacy_val.status, str) else privacy_val.status.value,
                "progress": privacy_val.progress,
                "mlflow_run_id": privacy_val.mlflow_run_id,
                "completed_at": privacy_val.completed_at.isoformat() if privacy_val.completed_at else None
            }
    
    return _json_safe(response)


@router.get("/suite/{suite_id}/privacy-details")
async def get_privacy_details(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed privacy validation results including PII detection,
    k-anonymity, l-diversity, recommendations, and warnings.
    """
    import json
    import mlflow
    from ..models.validation_suite import ValidationSuite
    
    # Get validation suite
    result = await db.execute(
        select(ValidationSuite).where(ValidationSuite.id == suite_id)
    )
    suite = result.scalar_one_or_none()
    
    if not suite:
        raise HTTPException(status_code=404, detail="Validation suite not found")
    
    # Verify access
    result = await db.execute(
        select(MLModel).where(MLModel.id == suite.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if not await verify_access(db, current_user, model.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get privacy validation
    if not suite.privacy_validation_id:
        raise HTTPException(status_code=404, detail="No privacy validation found for this suite")
    
    result = await db.execute(
        select(Validation).where(Validation.id == suite.privacy_validation_id)
    )
    privacy_val = result.scalar_one_or_none()
    
    if not privacy_val or not privacy_val.mlflow_run_id:
        raise HTTPException(status_code=404, detail="Privacy validation not completed or no MLflow run")
    
    # Load privacy report from MLflow artifact
    try:
        from ..config import settings
        import os
        
        # Try direct file access first (faster and avoids MLflow client issues)
        artifact_path = os.path.join(
            settings.mlflow_artifact_location,
            "1",  # Experiment ID
            privacy_val.mlflow_run_id,
            "artifacts",
            "privacy_report.json"
        )
        
        if os.path.exists(artifact_path):
            with open(artifact_path, 'r') as f:
                privacy_data = json.load(f)
            return privacy_data
        else:
            # Fallback to MLflow client
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            client = mlflow.tracking.MlflowClient()
            downloaded_path = client.download_artifacts(privacy_val.mlflow_run_id, "privacy_report.json")
            
            with open(downloaded_path, 'r') as f:
                privacy_data = json.load(f)
            
            return privacy_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load privacy details: {str(e)}")

@router.get("/suite/{suite_id}/transparency-details")
async def get_transparency_details(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed transparency validation results including:
    - Feature importance (SHAP values)
    - Model card
    - Performance metrics
    """
    from ..models.validation_suite import ValidationSuite
    import mlflow
    import json
    
    # Get validation suite
    result = await db.execute(
        select(ValidationSuite).where(ValidationSuite.id == suite_id)
    )
    suite = result.scalar_one_or_none()
    
    if not suite:
        raise HTTPException(status_code=404, detail="Validation suite not found")
    
    # Verify access
    result = await db.execute(
        select(MLModel).where(MLModel.id == suite.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if not await verify_access(db, current_user, model.project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not suite.transparency_validation_id:
        raise HTTPException(status_code=404, detail="No transparency validation found for this suite")
    
    result = await db.execute(
        select(Validation).where(Validation.id == suite.transparency_validation_id)
    )
    transparency_val = result.scalar_one_or_none()
    
    if not transparency_val or not transparency_val.mlflow_run_id:
        raise HTTPException(status_code=404, detail="Transparency validation not completed or no MLflow run")
    
    # Load transparency data from MLflow artifact
    try:
        from ..config import settings
        import os
        
        # FIX: Use absolute path based on this file's location to avoid working directory issues
        # Get the backend directory (2 levels up from this file: routers -> app -> backend)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        mlruns_dir = os.path.join(backend_dir, "mlruns")
        
        # Direct file access with absolute path
        artifact_base = os.path.join(
            mlruns_dir,
            "1",  # Experiment ID
            transparency_val.mlflow_run_id,
            "artifacts"
        )
        
        logger.info(f"Looking for transparency artifacts in: {artifact_base}")
        
        model_card_path = os.path.join(artifact_base, "model_card.json")
        feature_importance_path = os.path.join(artifact_base, "feature_importance.json")
        sample_predictions_path = os.path.join(artifact_base, "sample_predictions.json")
        transparency_warning_path = os.path.join(artifact_base, "transparency_warning.json")
        
        model_card = None
        feature_importance = {}
        sample_predictions = []
        transparency_warning = None
        
        if os.path.exists(model_card_path):
            with open(model_card_path, 'r') as f:
                model_card = json.load(f)
        
        if os.path.exists(feature_importance_path):
            with open(feature_importance_path, 'r') as f:
                feature_importance = json.load(f)
        
        if os.path.exists(sample_predictions_path):
            with open(sample_predictions_path, 'r') as f:
                sample_data = json.load(f)
                sample_predictions = sample_data.get("samples", [])
                transparency_warning = sample_data.get("warning")
                logger.info(f"Loaded {len(sample_predictions)} sample predictions from {sample_predictions_path}")
        else:
            logger.warning(f"Sample predictions file not found: {sample_predictions_path}")

        if not transparency_warning and os.path.exists(transparency_warning_path):
            with open(transparency_warning_path, 'r') as f:
                warning_data = json.load(f)
                transparency_warning = warning_data.get("warning")
        
        # FIX: Provide better error message showing what artifacts were found vs missing
        if not model_card and not feature_importance:
            missing_files = []
            if not os.path.exists(model_card_path):
                missing_files.append("model_card.json")
            if not os.path.exists(feature_importance_path):
                missing_files.append("feature_importance.json")
            
            error_detail = (
                f"Transparency artifacts not found. Missing files: {', '.join(missing_files)}. "
                f"The validation may have failed to save artifacts. "
                f"Searched in: {artifact_base}"
            )
            logger.error(error_detail)
            raise HTTPException(status_code=404, detail=error_detail)
        
        # Sort feature importance by value (descending)
        if feature_importance:
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )
            feature_importance = dict(sorted_features)
        
        return {
            "validation_id": str(transparency_val.id),
            "status": transparency_val.status.value if hasattr(transparency_val.status, 'value') else str(transparency_val.status),
            "mlflow_run_id": transparency_val.mlflow_run_id,
            "feature_importance": feature_importance,
            "model_card": model_card or {},
            "sample_predictions": sample_predictions,
            "warning": transparency_warning,
            "completed_at": transparency_val.completed_at.isoformat() if transparency_val.completed_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load transparency details: {str(e)}")