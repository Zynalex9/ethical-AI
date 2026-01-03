"""
Background tasks for running validations asynchronously.

These tasks are executed by Celery workers and allow long-running
validations to run without blocking HTTP requests.
"""

import os
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone

import pandas as pd
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models.validation import Validation, ValidationStatus, ValidationResult
from app.models.ml_model import MLModel
from app.models.dataset import Dataset
from app.models.audit_log import AuditLog, AuditAction, ResourceType
from app.services.model_loader import UniversalModelLoader
from app.validators.fairness_validator import FairnessValidator
from app.validators.explainability_engine import ExplainabilityEngine
from app.validators.privacy_validator import PrivacyValidator
from app.validators.accountability_tracker import AccountabilityTracker

logger = logging.getLogger(__name__)


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


# Core async validation functions (can be called directly or from Celery tasks)
async def _run_fairness_validation_async(
    db: AsyncSession,
    validation_id: str,
    model_id: str,
    dataset_id: str,
    sensitive_feature: str,
    target_column: str,
    thresholds: Optional[Dict[str, float]] = None,
    user_id: Optional[str] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """Core fairness validation logic (async)."""
    
    def _convert_to_json_serializable(obj):
        """Recursively convert numpy types to Python native types."""
        import numpy as np
        if isinstance(obj, dict):
            return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    try:
        # Update progress
        if progress_callback:
            progress_callback(10, "Loading model")
        
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
        
        if progress_callback:
            progress_callback(30, "Loading data")
        validation.progress = 30
        await db.commit()
        
        # Load dataset
        df = pd.read_csv(dataset_record.file_path)
        logger.info(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        
        # Check if target column is provided
        use_predictions_as_truth = target_column is None or target_column not in df.columns
        
        if use_predictions_as_truth:
            logger.warning("⚠️ NO TARGET COLUMN PROVIDED - Using prediction-only mode")
            logger.warning("⚠️ This mode checks if predictions are INTERNALLY FAIR, not if they match actual outcomes")
            logger.warning("⚠️ Results may be inaccurate without ground truth comparison")
            
            # Prepare features (all columns except sensitive feature)
            X = df.drop(columns=[sensitive_feature] if sensitive_feature in df.columns else [])
            sensitive = df[sensitive_feature].values
            
            logger.info(f"Features before encoding: {list(X.columns)}")
            logger.info(f"X shape before encoding: {X.shape}")
            
            # Handle non-numeric features
            for col in X.select_dtypes(include=['object']).columns:
                X[col] = pd.factorize(X[col])[0]
            
            logger.info(f"X shape after encoding: {X.shape}")
            
            # Load model and get predictions
            model = UniversalModelLoader.load(model_record.file_path)
            logger.info(f"Model loaded: {type(model).__name__}, wrapper type: {model.model_type}")
            
            # Feature matching
            model_obj = model._model if hasattr(model, '_model') else model
            if hasattr(model_obj, 'n_features_in_'):
                expected_features = model_obj.n_features_in_
                logger.info(f"Model expects {expected_features} features")
                
                if X.shape[1] != expected_features:
                    if hasattr(model_obj, 'feature_names_in_'):
                        model_features = list(model_obj.feature_names_in_)
                        logger.info(f"Model expects features: {model_features}")
                        missing_features = set(model_features) - set(X.columns)
                        if missing_features:
                            raise ValueError(f"Dataset is missing features: {missing_features}")
                        X = X[model_features]
                    else:
                        logger.warning(f"Using first {expected_features} features")
                        X = X.iloc[:, :expected_features]
            
            logger.info(f"Final X shape before prediction: {X.shape}")
            
            # Get predictions - use these as both y_true and y_pred
            y_pred = model.predict(X.values)
            y_true = y_pred.copy()  # Use predictions as "truth" for fairness comparison
            
            logger.info("ℹ️ MODE: Prediction-only fairness analysis")
            logger.info(f"Predictions distribution: {np.unique(y_pred, return_counts=True)}")
            logger.info("ℹ️ Fairness metrics will compare prediction consistency across groups")
            
        else:
            # Normal mode with ground truth
            logger.info(f"✓ TARGET COLUMN PROVIDED: {target_column}")
            logger.info("✓ MODE: Standard fairness analysis with ground truth comparison")
            
            # Prepare data
            X = df.drop(columns=[target_column])
            y_true_raw = df[target_column]
            sensitive = df[sensitive_feature].values
            
            # Encode target column to binary (0/1)
            if y_true_raw.dtype == 'object' or y_true_raw.dtype.name == 'category':
                logger.info(f"Target column unique values: {y_true_raw.unique()}")
                y_true = (y_true_raw.astype(str).str.contains('>|high|yes|true|1|approved', case=False, regex=True)).astype(int)
                logger.info(f"Encoded target to binary: {dict(zip(y_true_raw.unique(), [y_true[y_true_raw == val].iloc[0] if len(y_true[y_true_raw == val]) > 0 else None for val in y_true_raw.unique()]))}")
            else:
                y_true = y_true_raw.values
            
            logger.info(f"Features before encoding: {list(X.columns)}")
            logger.info(f"X shape before encoding: {X.shape}")
            
            # Handle non-numeric features
            for col in X.select_dtypes(include=['object']).columns:
                X[col] = pd.factorize(X[col])[0]
            
            logger.info(f"X shape after encoding: {X.shape}")
            
            # Load model
            model = UniversalModelLoader.load(model_record.file_path)
            logger.info(f"Model loaded: {type(model).__name__}, wrapper type: {model.model_type}")
            
            # Check if model has specific feature requirements
            model_obj = model._model if hasattr(model, '_model') else model
            if hasattr(model_obj, 'n_features_in_'):
                expected_features = model_obj.n_features_in_
                logger.info(f"Model expects {expected_features} features")
                
                if X.shape[1] != expected_features:
                    logger.warning(
                        f"Feature mismatch: model expects {expected_features} features, "
                        f"but dataset has {X.shape[1]} features after dropping target."
                    )
                    
                    # Try to match features if model has feature names
                    if hasattr(model_obj, 'feature_names_in_'):
                        model_features = list(model_obj.feature_names_in_)
                        logger.info(f"Model expects features: {model_features}")
                        
                        # Ensure we have all required features
                        missing_features = set(model_features) - set(X.columns)
                        if missing_features:
                            raise ValueError(
                                f"Dataset is missing features required by model: {missing_features}"
                            )
                        
                        # Select and order features to match model
                        X = X[model_features]
                        logger.info(f"Selected {len(model_features)} features matching model: {list(X.columns)}")
                    else:
                        # No feature names available, use first N features
                        logger.warning(
                            f"Model has no feature_names_in_, using first {expected_features} features"
                    )
                    original_cols = list(X.columns)
                    X = X.iloc[:, :expected_features]
                    logger.info(f"Selected first {expected_features} features: {list(X.columns)} (from {original_cols})")
            else:
                logger.info("Model has no n_features_in_ attribute, using all features")
            
            logger.info(f"Final X shape before prediction: {X.shape}")
            
            if progress_callback:
                progress_callback(50, "Running predictions")
            validation.progress = 50
            await db.commit()
            
            # Get predictions (only in normal mode, already done in prediction-only mode)
            y_pred = model.predict(X.values)
        
        # Ensure predictions are binary (0 or 1) for fairness metrics
        logger.info(f"Raw predictions - unique values: {np.unique(y_pred)}, dtype: {y_pred.dtype}")
        y_pred = np.asarray(y_pred, dtype=int)
        if not np.all(np.isin(y_pred, [0, 1])):
            logger.warning(f"Predictions contain non-binary values: {np.unique(y_pred)}, converting to binary")
            y_pred = (y_pred > 0.5).astype(int)
        logger.info(f"Final predictions - unique values: {np.unique(y_pred)}")
        
        # Ensure y_true is binary
        y_true_unique = np.unique(y_true)
        logger.info(f"y_true unique values: {y_true_unique}")
        if not np.all(np.isin(y_true, [0, 1])):
            logger.error(f"y_true contains non-binary values: {y_true_unique}")
            raise ValueError(f"Target values must be binary (0 or 1), got: {y_true_unique}")
        
        if progress_callback:
            progress_callback(70, "Calculating fairness metrics")
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
        
        # Convert report to dict and ensure JSON serializable
        report_dict = report.to_dict()
        report_dict = _convert_to_json_serializable(report_dict)
        tracker.log_dict(report_dict, "fairness_report.json")
        
        if progress_callback:
            progress_callback(90, "Saving results")
        validation.progress = 90
        await db.commit()
        
        # Save ValidationResult records to database for each metric
        logger.info("Saving validation results to database...")
        for metric in report.metrics:
            result_record = ValidationResult(
                validation_id=UUID(validation_id),
                principle="fairness",
                metric_name=metric.metric_name,
                metric_value=float(metric.overall_value) if metric.overall_value is not None else None,
                threshold=float(metric.threshold) if metric.threshold is not None else None,
                passed=bool(metric.passed),
                details={
                    "by_group": _convert_to_json_serializable(metric.by_group),
                    "description": metric.description
                }
            )
            db.add(result_record)
        await db.commit()
        logger.info(f"Saved {len(report.metrics)} validation results to database")
        
        # Log summary
        passed_count = sum(1 for m in report.metrics if m.passed)
        total_count = len(report.metrics)
        logger.info(f"Fairness validation complete. Passed: {passed_count}/{total_count} metrics. Overall: {'PASSED' if report.overall_passed else 'FAILED'}")
        
        # Update validation status
        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        validation.mlflow_run_id = tracker._current_run.info.run_id if tracker._current_run else None
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
        
        result_dict = {
            "validation_id": validation_id,
            "status": "completed",
            "overall_passed": report.overall_passed,
            "metrics": metrics,
            "group_metrics": {
                "groups": report.groups,
                "sample_sizes": report.sample_sizes
            },
            "mlflow_run_id": tracker._current_run.info.run_id if tracker._current_run else None
        }
        
        # Convert all numpy types to Python native types for JSON serialization
        return _convert_to_json_serializable(result_dict)
        
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
    
    def progress_callback(progress, step):
        self.update_state(state="PROGRESS", meta={"progress": progress, "step": step})
    
    async def _run():
        async with async_session_maker() as db:
            return await _run_fairness_validation_async(
                db=db,
                validation_id=validation_id,
                model_id=model_id,
                dataset_id=dataset_id,
                sensitive_feature=sensitive_feature,
                target_column=target_column,
                thresholds=thresholds,
                user_id=user_id,
                progress_callback=progress_callback
            )
    
    # Run async function using asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


async def _run_transparency_validation_async(
    db: AsyncSession,
    validation_id: str,
    model_id: str,
    dataset_id: str,
    target_column: str,
    sample_size: int = 100,
    user_id: Optional[str] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """Core transparency validation logic (async)."""
    try:
        if progress_callback:
            progress_callback(10, "Loading model")
        
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
        
        if progress_callback:
            progress_callback(30, "Loading data")
        validation.progress = 30
        await db.commit()
        
        # Load model and dataset
        model = UniversalModelLoader.load(model_record.file_path)
        df = pd.read_csv(dataset_record.file_path)
        
        # Prepare data
        X = df.drop(columns=[target_column])
        y = df[target_column]
        feature_names = X.columns.tolist()
        
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = pd.factorize(X[col])[0]
        
        # Encode target if it's categorical
        if y.dtype == 'object':
            y, _ = pd.factorize(y)
        
        X_values = X.values
        y_values = np.array(y)
        
        if progress_callback:
            progress_callback(50, "Sampling data")
        validation.progress = 50
        await db.commit()
        
        # Sample for performance
        sample_size = min(sample_size, len(X_values))
        indices = np.random.choice(len(X_values), sample_size, replace=False)
        X_sample = X_values[indices]
        y_sample = y_values[indices]
        
        if progress_callback:
            progress_callback(70, "Computing SHAP values")
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
        
        # Generate model card with proper parameters
        additional_info = {
            "model_name": model_record.name,
            "model_version": model_record.version,
            "intended_use": "Classification",
            "training_data_description": f"{dataset_record.name} ({dataset_record.row_count} samples)",
            "evaluation_data_description": f"{sample_size} samples"
        }
        model_card = engine.generate_model_card(
            X_test=X_sample,
            y_test=y_sample,
            additional_info=additional_info
        )
        
        # Log to MLflow
        importance_dict = {
            fi.feature_name: fi.importance
            for fi in global_exp.feature_importances
        }
        tracker.log_metrics(importance_dict)
        tracker.log_dict(model_card, "model_card.json")
        
        if progress_callback:
            progress_callback(90, "Saving results")
        validation.progress = 90
        await db.commit()
        
        # Update validation
        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        validation.mlflow_run_id = tracker._current_run.info.run_id if tracker._current_run else None
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
            "model_card": model_card,
            "mlflow_run_id": tracker._current_run.info.run_id if tracker._current_run else None
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


async def _run_privacy_validation_async(
    db: AsyncSession,
    validation_id: str,
    dataset_id: str,
    k_anonymity_k: int = 5,
    l_diversity_l: int = 2,
    quasi_identifiers: Optional[list] = None,
    sensitive_attribute: Optional[str] = None,
    user_id: Optional[str] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """Core privacy validation logic (async)."""
    try:
        if progress_callback:
            progress_callback(10, "Loading dataset")
        
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
        
        if progress_callback:
            progress_callback(30, "Loading data")
        validation.progress = 30
        await db.commit()
        
        # Load dataset
        df = pd.read_csv(dataset_record.file_path)
        
        if progress_callback:
            progress_callback(50, "Detecting PII")
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
        
        if progress_callback:
            progress_callback(70, "Running privacy checks")
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
        
        if progress_callback:
            progress_callback(90, "Saving results")
        validation.progress = 90
        await db.commit()
        
        # Update validation
        validation.status = ValidationStatus.COMPLETED
        validation.progress = 100
        validation.completed_at = datetime.now(timezone.utc)
        validation.mlflow_run_id = tracker._current_run.info.run_id if tracker._current_run else None
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
            "mlflow_run_id": tracker._current_run.info.run_id if tracker._current_run else None
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
    
    def progress_callback(progress, step):
        self.update_state(state="PROGRESS", meta={"progress": progress, "step": step})
    
    async def _run():
        async with async_session_maker() as db:
            return await _run_transparency_validation_async(
                db=db,
                validation_id=validation_id,
                model_id=model_id,
                dataset_id=dataset_id,
                target_column=target_column,
                sample_size=sample_size,
                user_id=user_id,
                progress_callback=progress_callback
            )
    
    # Run async function using asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


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
    
    def progress_callback(progress, step):
        self.update_state(state="PROGRESS", meta={"progress": progress, "step": step})
    
    async def _run():
        async with async_session_maker() as db:
            return await _run_privacy_validation_async(
                db=db,
                validation_id=validation_id,
                dataset_id=dataset_id,
                k_anonymity_k=k_anonymity_k,
                l_diversity_l=l_diversity_l,
                quasi_identifiers=quasi_identifiers,
                sensitive_attribute=sensitive_attribute,
                user_id=user_id,
                progress_callback=progress_callback
            )
    
    # Run async function using asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


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
    Run all validations in sequence.
    
    This is the main orchestrator task that runs:
    1. Fairness validation
    2. Transparency validation
    3. Privacy validation
    4. Accountability (tracked via MLflow in each validation)
    
    Returns aggregate results.
    """
    import asyncio
    from app.models.validation_suite import ValidationSuite
    
    async def _run():
        suite = None
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
                
                # 1. Fairness Validation (0-33%)
                self.update_state(state="PROGRESS", meta={"progress": 0, "step": "Starting fairness validation"})
                
                fairness_validation = Validation(
                    model_id=UUID(model_id),
                    dataset_id=UUID(dataset_id),
                    status=ValidationStatus.PENDING,
                    progress=0
                )
                db.add(fairness_validation)
                await db.commit()
                await db.refresh(fairness_validation)
                
                # Run fairness validation directly
                fairness_result = await _run_fairness_validation_async(
                    db=db,
                    validation_id=str(fairness_validation.id),
                    model_id=model_id,
                    dataset_id=dataset_id,
                    user_id=user_id,
                    progress_callback=lambda p, s: self.update_state(
                        state="PROGRESS", 
                        meta={"progress": int(p * 0.33), "step": f"Fairness: {s}"}
                    ),
                    **fairness_config
                )
                results["validations"]["fairness"] = fairness_result
                
                # 2. Transparency Validation (33-66%)
                self.update_state(state="PROGRESS", meta={"progress": 33, "step": "Starting transparency validation"})
                
                transparency_validation = Validation(
                    model_id=UUID(model_id),
                    dataset_id=UUID(dataset_id),
                    status=ValidationStatus.PENDING,
                    progress=0
                )
                db.add(transparency_validation)
                await db.commit()
                await db.refresh(transparency_validation)
                
                # Run transparency validation
                transparency_result = await _run_transparency_validation_async(
                    db=db,
                    validation_id=str(transparency_validation.id),
                    model_id=model_id,
                    dataset_id=dataset_id,
                    user_id=user_id,
                    progress_callback=lambda p, s: self.update_state(
                        state="PROGRESS",
                        meta={"progress": 33 + int(p * 0.33), "step": f"Transparency: {s}"}
                    ),
                    **transparency_config
                )
                results["validations"]["transparency"] = transparency_result
                
                # 3. Privacy Validation (66-100%)
                self.update_state(state="PROGRESS", meta={"progress": 66, "step": "Starting privacy validation"})
                
                privacy_validation = Validation(
                    model_id=UUID(model_id) if model_id else None,
                    dataset_id=UUID(dataset_id),
                    status=ValidationStatus.PENDING,
                    progress=0
                )
                db.add(privacy_validation)
                await db.commit()
                await db.refresh(privacy_validation)
                
                # Run privacy validation
                privacy_result = await _run_privacy_validation_async(
                    db=db,
                    validation_id=str(privacy_validation.id),
                    dataset_id=dataset_id,
                    user_id=user_id,
                    progress_callback=lambda p, s: self.update_state(
                        state="PROGRESS",
                        meta={"progress": 66 + int(p * 0.33), "step": f"Privacy: {s}"}
                    ),
                    **privacy_config
                )
                results["validations"]["privacy"] = privacy_result
                
                # 4. Calculate overall results
                self.update_state(state="PROGRESS", meta={"progress": 95, "step": "Finalizing results"})
                
                # Calculate overall pass/fail
                overall_passed = (
                    fairness_result.get("overall_passed", False) and
                    transparency_result.get("status") == "completed" and
                    privacy_result.get("overall_passed", False)
                )
                
                # Update suite
                suite.status = "completed"
                suite.overall_passed = overall_passed
                suite.fairness_validation_id = fairness_validation.id
                suite.transparency_validation_id = transparency_validation.id
                suite.privacy_validation_id = privacy_validation.id
                suite.completed_at = datetime.now(timezone.utc)
                await db.commit()
                
                results["overall_passed"] = overall_passed
                results["status"] = "completed"
                
                self.update_state(state="PROGRESS", meta={"progress": 100, "step": "Complete"})
                
                return results
                
            except Exception as e:
                logger.error(f"Validation suite failed: {str(e)}")
                # Update suite on error
                if suite is not None:
                    suite.status = "failed"
                    suite.error_message = str(e)
                    suite.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                raise
    
    # Run async function using asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
