# Validation router - Run validations via API

import os
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

router = APIRouter(prefix="/validate", tags=["validation"])


# Request/Response models
class FairnessValidationRequest(BaseModel):
    model_id: UUID
    dataset_id: UUID
    sensitive_feature: str
    target_column: str
    thresholds: Optional[Dict[str, float]] = None


class TransparencyValidationRequest(BaseModel):
    model_id: UUID
    dataset_id: UUID
    target_column: str
    sample_size: int = 100  # Number of samples for SHAP


class PrivacyValidationRequest(BaseModel):
    dataset_id: UUID
    k_anonymity_k: Optional[int] = 5
    l_diversity_l: Optional[int] = 2
    quasi_identifiers: Optional[List[str]] = None
    sensitive_attribute: Optional[str] = None


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
        
        report = validator.validate_all(thresholds=thresholds)
        
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
        # Update validation status on error
        validation.status = ValidationStatus.FAILED
        validation.error_message = str(e)
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


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
            for fi in global_exp.feature_importance
        }
        
        return TransparencyResultResponse(
            validation_id=validation.id,
            status="completed",
            global_importance=importance_dict,
            model_card=model_card.to_dict(),
            visualizations=global_exp.visualizations
        )
        
    except Exception as e:
        validation.status = ValidationStatus.FAILED
        validation.error_message = str(e)
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


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
        requirements: Dict[str, Any] = {'pii_detection': True}
        
        if request.quasi_identifiers:
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
            
            if request.sensitive_attribute:
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
        validation.status = ValidationStatus.FAILED
        validation.error_message = str(e)
        validation.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


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
    """Get validation history for a project."""
    if not await verify_access(db, current_user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get validations for models in this project
    result = await db.execute(
        select(Validation)
        .join(MLModel, Validation.model_id == MLModel.id, isouter=True)
        .join(Dataset, Validation.dataset_id == Dataset.id, isouter=True)
        .where(
            (MLModel.project_id == project_id) | (Dataset.project_id == project_id)
        )
        .order_by(Validation.started_at.desc())
        .limit(limit)
    )
    validations = result.scalars().all()
    
    return [
        {
            "id": v.id,
            "status": v.status.value,
            "progress": v.progress,
            "started_at": v.started_at,
            "completed_at": v.completed_at,
            "model_id": v.model_id,
            "dataset_id": v.dataset_id
        }
        for v in validations
    ]
class AllValidationsRequest(BaseModel):
    """Request to run all 4 validations in sequence."""
    model_id: UUID
    dataset_id: UUID
    fairness_config: Dict[str, Any]
    transparency_config: Dict[str, Any]
    privacy_config: Dict[str, Any]


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
        user_id=str(current_user.id)
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
        "started_at": suite.started_at,
        "completed_at": suite.completed_at,
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
            response["validations"]["fairness"] = {
                "validation_id": str(fairness_val.id),
                "status": fairness_val.status.value,
                "progress": fairness_val.progress,
                "mlflow_run_id": fairness_val.mlflow_run_id,
                "completed_at": fairness_val.completed_at
            }
    
    # Get transparency validation
    if suite.transparency_validation_id:
        result = await db.execute(
            select(Validation).where(Validation.id == suite.transparency_validation_id)
        )
        transparency_val = result.scalar_one_or_none()
        if transparency_val:
            response["validations"]["transparency"] = {
                "validation_id": str(transparency_val.id),
                "status": transparency_val.status.value,
                "progress": transparency_val.progress,
                "mlflow_run_id": transparency_val.mlflow_run_id,
                "completed_at": transparency_val.completed_at
            }
    
    # Get privacy validation
    if suite.privacy_validation_id:
        result = await db.execute(
            select(Validation).where(Validation.id == suite.privacy_validation_id)
        )
        privacy_val = result.scalar_one_or_none()
        if privacy_val:
            response["validations"]["privacy"] = {
                "validation_id": str(privacy_val.id),
                "status": privacy_val.status.value,
                "progress": privacy_val.progress,
                "mlflow_run_id": privacy_val.mlflow_run_id,
                "completed_at": privacy_val.completed_at
            }
    
    return response

