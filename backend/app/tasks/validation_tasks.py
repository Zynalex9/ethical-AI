"""
Background tasks for running validations asynchronously.

These tasks are executed by Celery workers and allow long-running
validations to run without blocking HTTP requests.
"""

import os
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone

import pandas as pd
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models.validation import Validation, ValidationStatus
from app.models.ml_model import MLModel
from app.models.dataset import Dataset
from app.models.audit_log import AuditLog, AuditAction, ResourceType
from app.services.model_loader import UniversalModelLoader
from app.validators.fairness_validator import FairnessValidator
from app.validators.explainability_engine import ExplainabilityEngine
from app.validators.privacy_validator import PrivacyValidator
from app.validators.accountability_tracker import AccountabilityTracker


# Create async engine for tasks
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db_session():
    """Get database session for tasks."""
    async with async_session_maker() as session:
        return session


@celery_app.task(bind=True, name="run_fairness_validation_task")
def run_fairness_validation_task(
    self,
    validation_id: str,
    model_id: str,
    dataset_id: str,
    sensitive_feature: str,
    target_column: str,
    thresholds: Optional[Dict[str, float]] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run fairness validation in background.
    
    Args:
        self: Celery task instance (for state updates)
        validation_id: UUID of validation record
        model_id: UUID of model
        dataset_id: UUID of dataset
        sensitive_feature: Column name for sensitive attribute
        target_column: Column name for target variable
        thresholds: Optional fairness thresholds
        user_id: Optional user ID for audit
        
    Returns:
        Dictionary with validation results
    """
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            try:
                # Update task state
                self.update_state(state="PROGRESS", meta={"progress": 10, "step": "Loading model"})
                
                # Get validation record
                result = await db.execute(
                    select(Validation).where(Validation.id == UUID(validation_id))
                )
                validation = result.scalar_one()
                validation.status = ValidationStatus.RUNNING
                validation.progress = 10
                await db.commit()
                
                # Get model
                result = await db.execute(
                    select(MLModel).where(MLModel.id == UUID(model_id))
                )
                model_record = result.scalar_one()
                
                # Get dataset
                result = await db.execute(
                    select(Dataset).where(Dataset.id == UUID(dataset_id))
                )
                dataset_record = result.scalar_one()
                
                # Initialize accountability tracker
                tracker = AccountabilityTracker(
                    tracking_uri=settings.mlflow_tracking_uri,
                    experiment_name=settings.mlflow_experiment_name,
                    use_mlflow=True
                )
                
                tracker.start_validation_run(
                    model_name=model_record.name,
                    model_id=model_id,
                    dataset_name=dataset_record.name,
                    dataset_id=dataset_id,
                    requirement_name="Fairness Validation",
                    requirement_id=validation_id,
                    principle="fairness",
                    user_id=user_id
                )
                
                self.update_state(state="PROGRESS", meta={"progress": 30, "step": "Loading data"})
                validation.progress = 30
                await db.commit()
                
                # Load model
                model = UniversalModelLoader.load(model_record.file_path)
                
                # Load dataset
                df = pd.read_csv(dataset_record.file_path)
                
                # Prepare data
                X = df.drop(columns=[target_column])
                y_true = df[target_column].values
                sensitive = df[sensitive_feature].values
                
                # Handle non-numeric features
                for col in X.select_dtypes(include=['object']).columns:
                    X[col] = pd.factorize(X[col])[0]
                
                self.update_state(state="PROGRESS", meta={"progress": 50, "step": "Running predictions"})
                validation.progress = 50
                await db.commit()
                
                # Get predictions
                y_pred = model.predict(X.values)
                
                self.update_state(state="PROGRESS", meta={"progress": 70, "step": "Calculating fairness metrics"})
                validation.progress = 70
                await db.commit()
                
                # Run fairness validation
                thresholds = thresholds or {
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
                
                # Log metrics to MLflow
                metrics_dict = {
                    m.metric_name: m.overall_value
                    for m in report.metrics
                }
                tracker.log_metrics(metrics_dict)
                tracker.log_dict(report.to_dict(), "fairness_report.json")
                
                self.update_state(state="PROGRESS", meta={"progress": 90, "step": "Saving results"})
                validation.progress = 90
                await db.commit()
                
                # Update validation status
                validation.status = ValidationStatus.COMPLETED
                validation.progress = 100
                validation.completed_at = datetime.now(timezone.utc)
                validation.mlflow_run_id = tracker.current_run_id
                await db.commit()
                
                # End MLflow run
                tracker.end_validation_run(
                    status="passed" if report.overall_passed else "failed"
                )
                
                # Create audit log
                if user_id:
                    audit = AuditLog(
                        user_id=UUID(user_id),
                        action=AuditAction.VALIDATION_RUN,
                        resource_type=ResourceType.VALIDATION,
                        resource_id=UUID(validation_id),
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
                
                return {
                    "validation_id": validation_id,
                    "status": "completed",
                    "overall_passed": report.overall_passed,
                    "metrics": metrics,
                    "group_metrics": {
                        "groups": report.groups,
                        "sample_sizes": report.sample_sizes
                    },
                    "mlflow_run_id": tracker.current_run_id
                }
                
            except Exception as e:
                # Update validation on error
                validation.status = ValidationStatus.FAILED
                validation.error_message = str(e)
                validation.completed_at = datetime.now(timezone.utc)
                await db.commit()
                
                # End MLflow run with error
                try:
                    tracker.end_validation_run(status="error", error_message=str(e))
                except:
                    pass
                
                raise
    
    # Run async function
    return asyncio.run(_run())


@celery_app.task(bind=True, name="run_transparency_validation_task")
def run_transparency_validation_task(
    self,
    validation_id: str,
    model_id: str,
    dataset_id: str,
    target_column: str,
    sample_size: int = 100,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Run transparency/explainability validation in background."""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            try:
                self.update_state(state="PROGRESS", meta={"progress": 10, "step": "Loading model"})
                
                # Get validation record
                result = await db.execute(
                    select(Validation).where(Validation.id == UUID(validation_id))
                )
                validation = result.scalar_one()
                validation.status = ValidationStatus.RUNNING
                validation.progress = 10
                await db.commit()
                
                # Get model and dataset
                result = await db.execute(
                    select(MLModel).where(MLModel.id == UUID(model_id))
                )
                model_record = result.scalar_one()
                
                result = await db.execute(
                    select(Dataset).where(Dataset.id == UUID(dataset_id))
                )
                dataset_record = result.scalar_one()
                
                # Initialize accountability tracker
                tracker = AccountabilityTracker(
                    tracking_uri=settings.mlflow_tracking_uri,
                    experiment_name=settings.mlflow_experiment_name,
                    use_mlflow=True
                )
                
                tracker.start_validation_run(
                    model_name=model_record.name,
                    model_id=model_id,
                    dataset_name=dataset_record.name,
                    dataset_id=dataset_id,
                    requirement_name="Transparency Validation",
                    requirement_id=validation_id,
                    principle="transparency",
                    user_id=user_id
                )
                
                self.update_state(state="PROGRESS", meta={"progress": 30, "step": "Loading data"})
                validation.progress = 30
                await db.commit()
                
                # Load model and dataset
                model = UniversalModelLoader.load(model_record.file_path)
                df = pd.read_csv(dataset_record.file_path)
                
                # Prepare data
                X = df.drop(columns=[target_column])
                feature_names = X.columns.tolist()
                
                for col in X.select_dtypes(include=['object']).columns:
                    X[col] = pd.factorize(X[col])[0]
                
                X_values = X.values
                
                self.update_state(state="PROGRESS", meta={"progress": 50, "step": "Sampling data"})
                validation.progress = 50
                await db.commit()
                
                # Sample for performance
                sample_size = min(sample_size, len(X_values))
                indices = np.random.choice(len(X_values), sample_size, replace=False)
                X_sample = X_values[indices]
                
                self.update_state(state="PROGRESS", meta={"progress": 70, "step": "Computing SHAP values"})
                validation.progress = 70
                await db.commit()
                
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
                
                # Log to MLflow
                importance_dict = {
                    fi.feature_name: fi.importance
                    for fi in global_exp.feature_importance
                }
                tracker.log_metrics(importance_dict)
                tracker.log_dict(model_card.to_dict(), "model_card.json")
                
                self.update_state(state="PROGRESS", meta={"progress": 90, "step": "Saving results"})
                validation.progress = 90
                await db.commit()
                
                # Update validation
                validation.status = ValidationStatus.COMPLETED
                validation.progress = 100
                validation.completed_at = datetime.now(timezone.utc)
                validation.mlflow_run_id = tracker.current_run_id
                await db.commit()
                
                tracker.end_validation_run(status="passed")
                
                # Audit log
                if user_id:
                    audit = AuditLog(
                        user_id=UUID(user_id),
                        action=AuditAction.VALIDATION_RUN,
                        resource_type=ResourceType.VALIDATION,
                        resource_id=UUID(validation_id),
                        details={
                            "validation_type": "transparency",
                            "model_name": model_record.name,
                            "sample_size": sample_size
                        }
                    )
                    db.add(audit)
                    await db.commit()
                
                return {
                    "validation_id": validation_id,
                    "status": "completed",
                    "global_importance": importance_dict,
                    "model_card": model_card.to_dict(),
                    "mlflow_run_id": tracker.current_run_id
                }
                
            except Exception as e:
                validation.status = ValidationStatus.FAILED
                validation.error_message = str(e)
                validation.completed_at = datetime.now(timezone.utc)
                await db.commit()
                
                try:
                    tracker.end_validation_run(status="error", error_message=str(e))
                except:
                    pass
                
                raise
    
    return asyncio.run(_run())


@celery_app.task(bind=True, name="run_privacy_validation_task")
def run_privacy_validation_task(
    self,
    validation_id: str,
    dataset_id: str,
    k_anonymity_k: int = 5,
    l_diversity_l: int = 2,
    quasi_identifiers: Optional[list] = None,
    sensitive_attribute: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Run privacy validation in background."""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            try:
                self.update_state(state="PROGRESS", meta={"progress": 10, "step": "Loading dataset"})
                
                # Get validation record
                result = await db.execute(
                    select(Validation).where(Validation.id == UUID(validation_id))
                )
                validation = result.scalar_one()
                validation.status = ValidationStatus.RUNNING
                validation.progress = 10
                await db.commit()
                
                # Get dataset
                result = await db.execute(
                    select(Dataset).where(Dataset.id == UUID(dataset_id))
                )
                dataset_record = result.scalar_one()
                
                # Initialize accountability tracker
                tracker = AccountabilityTracker(
                    tracking_uri=settings.mlflow_tracking_uri,
                    experiment_name=settings.mlflow_experiment_name,
                    use_mlflow=True
                )
                
                tracker.start_validation_run(
                    model_name="N/A",
                    model_id="N/A",
                    dataset_name=dataset_record.name,
                    dataset_id=dataset_id,
                    requirement_name="Privacy Validation",
                    requirement_id=validation_id,
                    principle="privacy",
                    user_id=user_id
                )
                
                self.update_state(state="PROGRESS", meta={"progress": 30, "step": "Loading data"})
                validation.progress = 30
                await db.commit()
                
                # Load dataset
                df = pd.read_csv(dataset_record.file_path)
                
                self.update_state(state="PROGRESS", meta={"progress": 50, "step": "Detecting PII"})
                validation.progress = 50
                await db.commit()
                
                # Initialize privacy validator
                validator = PrivacyValidator(df)
                
                # Build requirements
                requirements = {'pii_detection': True}
                
                if quasi_identifiers:
                    requirements['k_anonymity'] = {
                        'k': k_anonymity_k,
                        'quasi_identifiers': quasi_identifiers
                    }
                    
                    if sensitive_attribute:
                        requirements['l_diversity'] = {
                            'l': l_diversity_l,
                            'quasi_identifiers': quasi_identifiers,
                            'sensitive_attribute': sensitive_attribute
                        }
                
                self.update_state(state="PROGRESS", meta={"progress": 70, "step": "Running privacy checks"})
                validation.progress = 70
                await db.commit()
                
                # Run validation
                report = validator.validate(requirements)
                
                # Log to MLflow
                metrics = {
                    "pii_detected_count": len([r for r in report.pii_results if r.is_pii]),
                    "overall_passed": 1.0 if report.overall_passed else 0.0
                }
                if report.k_anonymity:
                    metrics["k_anonymity_satisfied"] = 1.0 if report.k_anonymity.satisfies_k else 0.0
                if report.l_diversity:
                    metrics["l_diversity_satisfied"] = 1.0 if report.l_diversity.satisfies_l else 0.0
                
                tracker.log_metrics(metrics)
                tracker.log_dict(report.to_dict(), "privacy_report.json")
                
                self.update_state(state="PROGRESS", meta={"progress": 90, "step": "Saving results"})
                validation.progress = 90
                await db.commit()
                
                # Update validation
                validation.status = ValidationStatus.COMPLETED
                validation.progress = 100
                validation.completed_at = datetime.now(timezone.utc)
                validation.mlflow_run_id = tracker.current_run_id
                await db.commit()
                
                tracker.end_validation_run(
                    status="passed" if report.overall_passed else "failed"
                )
                
                # Audit log
                if user_id:
                    audit = AuditLog(
                        user_id=UUID(user_id),
                        action=AuditAction.VALIDATION_RUN,
                        resource_type=ResourceType.VALIDATION,
                        resource_id=UUID(validation_id),
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
                
                return {
                    "validation_id": validation_id,
                    "status": "completed",
                    "overall_passed": report.overall_passed,
                    "pii_detected": pii_list,
                    "k_anonymity": report.k_anonymity.to_dict() if report.k_anonymity else None,
                    "l_diversity": report.l_diversity.to_dict() if report.l_diversity else None,
                    "recommendations": report.recommendations,
                    "mlflow_run_id": tracker.current_run_id
                }
                
            except Exception as e:
                validation.status = ValidationStatus.FAILED
                validation.error_message = str(e)
                validation.completed_at = datetime.now(timezone.utc)
                await db.commit()
                
                try:
                    tracker.end_validation_run(status="error", error_message=str(e))
                except:
                    pass
                
                raise
    
    return asyncio.run(_run())


@celery_app.task(bind=True, name="run_all_validations_task")
def run_all_validations_task(
    self,
    suite_id: str,
    model_id: str,
    dataset_id: str,
    fairness_config: Dict[str, Any],
    transparency_config: Dict[str, Any],
    privacy_config: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run all 4 validations in sequence.
    
    This is the main orchestrator task that runs:
    1. Fairness validation
    2. Transparency validation
    3. Privacy validation
    4. Accountability (tracked via MLflow)
    
    Returns aggregate results.
    """
    import asyncio
    from app.models.validation_suite import ValidationSuite
    
    async def _run():
        async with async_session_maker() as db:
            try:
                # Get validation suite
                result = await db.execute(
                    select(ValidationSuite).where(ValidationSuite.id == UUID(suite_id))
                )
                suite = result.scalar_one()
                
                results = {
                    "suite_id": suite_id,
                    "validations": {}
                }
                
                # 1. Fairness Validation
                self.update_state(state="PROGRESS", meta={"progress": 10, "step": "Fairness validation"})
                
                fairness_validation = Validation(
                    model_id=UUID(model_id),
                    dataset_id=UUID(dataset_id),
                    status=ValidationStatus.PENDING,
                    progress=0
                )
                db.add(fairness_validation)
                await db.commit()
                await db.refresh(fairness_validation)
                
                fairness_result = run_fairness_validation_task(
                    validation_id=str(fairness_validation.id),
                    model_id=model_id,
                    dataset_id=dataset_id,
                    user_id=user_id,
                    **fairness_config
                )
                results["validations"]["fairness"] = fairness_result
                
                # 2. Transparency Validation
                self.update_state(state="PROGRESS", meta={"progress": 35, "step": "Transparency validation"})
                
                transparency_validation = Validation(
                    model_id=UUID(model_id),
                    dataset_id=UUID(dataset_id),
                    status=ValidationStatus.PENDING,
                    progress=0
                )
                db.add(transparency_validation)
                await db.commit()
                await db.refresh(transparency_validation)
                
                transparency_result = run_transparency_validation_task(
                    validation_id=str(transparency_validation.id),
                    model_id=model_id,
                    dataset_id=dataset_id,
                    user_id=user_id,
                    **transparency_config
                )
                results["validations"]["transparency"] = transparency_result
                
                # 3. Privacy Validation
                self.update_state(state="PROGRESS", meta={"progress": 70, "step": "Privacy validation"})
                
                privacy_validation = Validation(
                    dataset_id=UUID(dataset_id),
                    status=ValidationStatus.PENDING,
                    progress=0
                )
                db.add(privacy_validation)
                await db.commit()
                await db.refresh(privacy_validation)
                
                privacy_result = run_privacy_validation_task(
                    validation_id=str(privacy_validation.id),
                    dataset_id=dataset_id,
                    user_id=user_id,
                    **privacy_config
                )
                results["validations"]["privacy"] = privacy_result
                
                # Update suite
                self.update_state(state="PROGRESS", meta={"progress": 95, "step": "Finalizing"})
                
                # Calculate overall pass/fail
                overall_passed = all([
                    fairness_result.get("overall_passed", False),
                    privacy_result.get("overall_passed", False)
                ])
                
                suite.status = "completed"
                suite.overall_passed = overall_passed
                suite.fairness_validation_id = fairness_validation.id
                suite.transparency_validation_id = transparency_validation.id
                suite.privacy_validation_id = privacy_validation.id
                suite.completed_at = datetime.now(timezone.utc)
                await db.commit()
                
                results["overall_passed"] = overall_passed
                results["status"] = "completed"
                
                return results
                
            except Exception as e:
                # Update suite on error
                suite.status = "failed"
                suite.error_message = str(e)
                suite.completed_at = datetime.now(timezone.utc)
                await db.commit()
                raise
    
    return asyncio.run(_run())
