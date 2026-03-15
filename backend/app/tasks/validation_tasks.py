"""
Background tasks for running validations asynchronously.

These tasks are executed by Celery workers and allow long-running
validations to run without blocking HTTP requests.
"""

import os
import logging
import asyncio
from pathlib import Path
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


def _safe_error_message(e: Exception, max_length: int = 2000) -> str:
    """Truncate error messages to prevent DB column overflow."""
    msg = str(e)
    if len(msg) > max_length:
        return msg[:max_length - 50] + f"... [truncated, total {len(msg)} chars]"
    return msg


def _resolve_dataset_file_path(stored_path: str) -> str:
    """Resolve dataset path robustly for worker context (handles legacy relative paths)."""
    p = Path(stored_path)
    if p.is_absolute():
        return str(p)

    # Legacy records may store paths like 'uploads/datasets/...'.
    backend_dir = Path(settings.upload_dir).resolve().parent
    candidate_from_backend = (backend_dir / p).resolve()
    if candidate_from_backend.exists():
        return str(candidate_from_backend)

    # Fallback: treat as relative to upload dir.
    candidate_from_uploads = (Path(settings.upload_dir).resolve() / p).resolve()
    return str(candidate_from_uploads)


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

# Reuse one event loop per Celery worker process.
# Creating and closing a fresh loop per task can leave pooled asyncpg
# connections bound to a closed loop, causing intermittent failures on
# subsequent tasks (e.g. 'NoneType' object has no attribute 'send').
_TASK_LOOP: Optional[asyncio.AbstractEventLoop] = None


def _run_async_in_task_loop(coro: Any) -> Any:
    """Run coroutine on a persistent process-local asyncio loop."""
    global _TASK_LOOP
    if _TASK_LOOP is None or _TASK_LOOP.is_closed():
        _TASK_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(_TASK_LOOP)
    return _TASK_LOOP.run_until_complete(coro)


async def get_db_session():
    """Get database session for tasks."""
    async with async_session_maker() as session:
        return session


def _align_features_to_model(
    X: pd.DataFrame,
    model: Any,
    context: str = "validation",
    allow_missing_fill: bool = True,
) -> pd.DataFrame:
    """Align dataset features with model schema.

    - If model exposes feature_names_in_, reorder and drop extras by name.
    - Missing named features are filled with 0 when allow_missing_fill=True.
    - Else if model exposes n_features_in_, trim extras by position.
    - Missing positional features are padded with 0 when allow_missing_fill=True.
    """
    model_obj = model._model if hasattr(model, '_model') else model

    if hasattr(model_obj, 'feature_names_in_'):
        model_features = [str(f) for f in list(model_obj.feature_names_in_)]
        missing = [f for f in model_features if f not in X.columns]
        if missing:
            if allow_missing_fill:
                logger.warning(
                    f"{context}: filling missing model features with 0: {missing[:15]}"
                )
                for feature in missing:
                    X[feature] = 0.0
            else:
                available_preview = ", ".join(list(X.columns)[:15])
                raise ValueError(
                    f"{context}: dataset is missing required model features: {missing}. "
                    f"Available columns (first 15): {available_preview}"
                )

        extra = [c for c in X.columns if c not in model_features]
        if extra:
            logger.info(f"{context}: dropping extra columns not used by model: {extra[:15]}")

        return X[model_features]

    if hasattr(model_obj, 'n_features_in_'):
        expected_features = int(model_obj.n_features_in_)
        if X.shape[1] < expected_features:
            if allow_missing_fill:
                missing_count = expected_features - X.shape[1]
                logger.warning(
                    f"{context}: model expects {expected_features} features, got {X.shape[1]}; "
                    f"padding {missing_count} synthetic feature(s) with 0"
                )
                for i in range(missing_count):
                    X[f"__pad_feature_{i}"] = 0.0
            else:
                raise ValueError(
                    f"{context}: model expects {expected_features} features, "
                    f"but dataset has only {X.shape[1]} after preprocessing"
                )
        if X.shape[1] > expected_features:
            logger.warning(
                f"{context}: model expects {expected_features} features, got {X.shape[1]}; "
                f"dropping {X.shape[1] - expected_features} extra columns by position"
            )
            return X.iloc[:, :expected_features]

    return X


# Core async validation functions (can be called directly or from Celery tasks)
async def _run_fairness_validation_async(
    db: AsyncSession,
    validation_id: str,
    model_id: str,
    dataset_id: str,
    sensitive_feature: str,
    target_column: str,
    thresholds: Optional[Dict[str, float]] = None,
    selected_metrics: Optional[list] = None,
    user_id: Optional[str] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """Core fairness validation logic (async)."""
    validation: Optional[Validation] = None
    tracker: Optional[AccountabilityTracker] = None
    
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
        resolved_dataset_path = _resolve_dataset_file_path(dataset_record.file_path)
        if not os.path.exists(resolved_dataset_path):
            raise FileNotFoundError(
                "Dataset file not found on disk for validation. "
                f"Stored path: '{dataset_record.file_path}', resolved path: '{resolved_dataset_path}'. "
                "Re-upload or re-load this dataset and try again."
            )
        df = pd.read_csv(resolved_dataset_path)
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
            
            # Feature matching (resilient mode: fill missing with zeros, drop extras)
            X = _align_features_to_model(X, model, context="fairness(prediction-only)", allow_missing_fill=True)
            
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
            
            # Feature matching (resilient mode: fill missing with zeros, drop extras)
            X = _align_features_to_model(X, model, context="fairness", allow_missing_fill=True)
            
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
            n_unique = len(y_true_unique)
            sample = y_true_unique[:10].tolist()
            logger.error(f"y_true contains non-binary values: {n_unique} unique values, sample: {sample}")
            raise ValueError(
                f"Target values must be binary (0 or 1), got {n_unique} unique values. "
                f"Sample: {sample}. Encode the target column to 0/1 before validation."
            )
        
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
        
        report = validator.validate_all(
            thresholds=thresholds,
            selected_metrics=selected_metrics,
        )
        
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
        
        # Save confusion matrices as a special ValidationResult record
        confusion_matrices_data = {
            cm.group_name: {
                "tp": int(cm.tp),
                "fp": int(cm.fp),
                "tn": int(cm.tn),
                "fn": int(cm.fn),
                "accuracy": float(cm.accuracy),
                "tpr": float(cm.tpr),
                "fpr": float(cm.fpr)
            }
            for cm in report.confusion_matrices
        }
        
        confusion_result = ValidationResult(
            validation_id=UUID(validation_id),
            principle="fairness",
            metric_name="group_confusion_matrices",  # Match frontend expectation
            metric_value=None,  # No single scalar value
            threshold=None,
            passed=True,  # Always passes, just informational
            details=_convert_to_json_serializable(confusion_matrices_data)
        )
        db.add(confusion_result)
        
        await db.commit()
        logger.info(f"Saved {len(report.metrics)} validation results and confusion matrices to database")
        
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
        
        # Format confusion matrices for frontend
        confusion_matrices = [
            {
                "group": cm.group_name,
                "tp": cm.tp,
                "fp": cm.fp,
                "tn": cm.tn,
                "fn": cm.fn
            }
            for cm in report.confusion_matrices
        ]
        
        result_dict = {
            "validation_id": validation_id,
            "status": "completed",
            "overall_passed": report.overall_passed,
            "metrics": metrics,
            "confusion_matrices": confusion_matrices,
            "group_metrics": {
                "groups": report.groups,
                "sample_sizes": report.sample_sizes
            },
            "mlflow_run_id": tracker._current_run.info.run_id if tracker._current_run else None
        }
        
        # Convert all numpy types to Python native types for JSON serialization
        return _convert_to_json_serializable(result_dict)
        
    except Exception as e:
        # Update validation on error with rollback recovery
        try:
            await db.rollback()
            if validation is not None:
                validation.status = ValidationStatus.FAILED
                validation.error_message = _safe_error_message(e)
                validation.completed_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception as db_err:
            logger.error(f"Failed to persist fairness error state: {db_err}")
        
        # End MLflow run with error
        try:
            if tracker is not None:
                tracker.end_validation_run(status="error", error_message=_safe_error_message(e))
        except Exception:
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
    selected_metrics: Optional[list] = None,
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
                selected_metrics=selected_metrics,
                user_id=user_id,
                progress_callback=progress_callback
            )
    
    return _run_async_in_task_loop(_run())


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
    validation: Optional[Validation] = None
    tracker: Optional[AccountabilityTracker] = None
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

        # If target column is not provided, skip transparency instead of failing the suite.
        if not target_column:
            validation.status = ValidationStatus.CANCELLED
            validation.progress = 100
            validation.error_message = "Transparency validation skipped: target column not provided."
            validation.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {
                "validation_id": validation_id,
                "status": "skipped",
                "skipped": True,
                "message": "Transparency validation skipped because target column was not selected."
            }
        
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
        
        # FIX: Add debugging to verify tracker is working
        logger.info(f"🔍 MLflow tracker initialized: use_mlflow={tracker.use_mlflow}, _mlflow={tracker._mlflow is not None}")
        
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
        
        # FIX: Verify run was started
        if tracker._current_run:
            logger.info(f"✅ MLflow run started: {tracker._current_run.info.run_id}")
        else:
            logger.error("❌ Failed to start MLflow run!")
        
        if progress_callback:
            progress_callback(30, "Loading data")
        validation.progress = 30
        await db.commit()
        
        # Load model and dataset
        model = UniversalModelLoader.load(model_record.file_path)
        resolved_dataset_path = _resolve_dataset_file_path(dataset_record.file_path)
        if not os.path.exists(resolved_dataset_path):
            raise FileNotFoundError(
                "Dataset file not found on disk for validation. "
                f"Stored path: '{dataset_record.file_path}', resolved path: '{resolved_dataset_path}'. "
                "Re-upload or re-load this dataset and try again."
            )
        df = pd.read_csv(resolved_dataset_path)
        
        # FIX: Validate that target column exists in dataset
        if target_column not in df.columns:
            available_columns = ", ".join(df.columns.tolist()[:10])
            raise ValueError(
                f"Target column '{target_column}' not found in dataset. "
                f"Available columns: {available_columns}..."
            )
        
        # Prepare data
        X = df.drop(columns=[target_column])
        y = df[target_column]
        
        for col in X.select_dtypes(include=['object']).columns:
            X[col] = pd.factorize(X[col])[0]

        # Align to model feature schema (drop extras / reorder / validate missing)
        X = _align_features_to_model(X, model, context="transparency", allow_missing_fill=True)
        feature_names = X.columns.tolist()
        
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
        
        # Build importance dictionary from SHAP results
        importance_dict = {
            fi.feature_name: fi.importance
            for fi in global_exp.feature_importances
        }
        logger.info(f"📊 Built feature importance dict with {len(importance_dict)} features")
        
        # Log metrics to MLflow (with sanitized names for MLflow compatibility)
        try:
            # MLflow metric names can't contain spaces or special chars, so sanitize them
            sanitized_metrics = {
                key.replace(" ", "_").replace("-", "_").replace(".", "_"): float(value)
                for key, value in importance_dict.items()
            }
            tracker.log_metrics(sanitized_metrics)
            logger.info(f"✅ Logged {len(sanitized_metrics)} metrics to MLflow")
        except Exception as e:
            logger.warning(f"⚠️ Failed to log metrics (non-fatal): {str(e)}")
        
        # Save transparency artifacts to MLflow
        logger.info("💾 Saving transparency artifacts to MLflow...")
        
        try:
            logger.info(f"  → Saving feature_importance.json ({len(importance_dict)} features)...")
            tracker.log_dict(importance_dict, "feature_importance.json")
            logger.info("  ✅ feature_importance.json saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to save feature_importance.json: {str(e)}", exc_info=True)
        
        try:
            logger.info(f"  → Saving model_card.json...")
            tracker.log_dict(model_card, "model_card.json")
            logger.info("  ✅ model_card.json saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to save model_card.json: {str(e)}", exc_info=True)
        
        logger.info("✅ Transparency artifact saving complete")
        
        # Generate sample local explanations (Phase 2)
        sample_predictions = []
        transparency_warning: Optional[str] = None
        num_samples = min(5, len(X_sample))  # Get 5 example predictions
        sample_indices = np.random.choice(len(X_sample), num_samples, replace=False).tolist()
        
        try:
            # Get local explanations for all samples at once
            local_explanations = engine.explain_local_shap(X_sample, instance_indices=sample_indices)
            
            for local_exp in local_explanations:
                idx = local_exp.instance_index
                y_true = int(y_sample[idx])
                
                # Get feature contributions from the LocalExplanation
                contributions = {}
                for feature_name, shap_value in local_exp.feature_contributions.items():
                    feature_idx = feature_names.index(feature_name) if feature_name in feature_names else -1
                    if feature_idx >= 0:
                        contributions[feature_name] = {
                            "value": float(X_sample[idx][feature_idx]),
                            "shap_contribution": float(shap_value)
                        }
                
                # Sort by absolute contribution and take top 5
                sorted_contributions = sorted(
                    contributions.items(),
                    key=lambda x: abs(x[1]["shap_contribution"]),
                    reverse=True
                )[:5]
                
                sample_predictions.append({
                    "sample_index": int(idx),
                    "true_label": y_true,
                    "predicted_label": int(local_exp.prediction),
                    "correct": bool(y_true == local_exp.prediction),
                    "top_features": {k: v for k, v in sorted_contributions},
                    "base_value": float(local_exp.base_value)
                })
            
            logger.info(f"Generated {len(sample_predictions)} sample local explanations")
        except Exception as e:
            logger.error(f"Failed to generate sample local explanations: {str(e)}", exc_info=True)
        
        # Save sample predictions
        if sample_predictions:
            logger.info(f"💾 Saving {len(sample_predictions)} sample predictions...")
            tracker.log_dict({"samples": sample_predictions}, "sample_predictions.json")
        else:
            logger.warning("⚠️ No sample predictions were generated")
        
        # ── LIME local explanations + Explanation Fidelity ────────────
        lime_explanations_serialized = []
        explanation_fidelity = None
        try:
            logger.info("🍋 Computing LIME local explanations...")
            lime_explanations = engine.explain_local_lime(X_sample, instance_indices=sample_indices)
            for lime_exp in lime_explanations:
                idx = lime_exp.instance_index
                lime_explanations_serialized.append({
                    "sample_index": int(idx),
                    "predicted_label": int(lime_exp.prediction),
                    "prediction_probability": float(lime_exp.prediction_probability),
                    "feature_contributions": {
                        k: float(v) for k, v in lime_exp.feature_contributions.items()
                    },
                    "explanation_type": "lime"
                })
            logger.info(f"✅ Generated {len(lime_explanations_serialized)} LIME explanations")

            # Compute explanation fidelity: 1 − mean(|f(x) − g(x)|)
            logger.info("📐 Computing explanation fidelity...")
            explanation_fidelity = engine.compute_explanation_fidelity(
                X_sample, instance_indices=sample_indices
            )
            logger.info(f"✅ Explanation fidelity = {explanation_fidelity:.4f}")

            # Save LIME artifacts to MLflow
            tracker.log_dict({"lime_explanations": lime_explanations_serialized}, "lime_explanations.json")
            tracker.log_metrics({"explanation_fidelity": explanation_fidelity})
        except Exception as e:
            logger.warning(f"⚠️ LIME / fidelity computation failed (non-fatal): {e}", exc_info=True)

        # Detect potentially invalid explanations: all SHAP/LIME contributions are approximately zero.
        shap_values = [
            float(feature_info.get("shap_contribution", 0.0))
            for sample in sample_predictions
            for feature_info in sample.get("top_features", {}).values()
        ]
        lime_values = [
            float(v)
            for lime in lime_explanations_serialized
            for v in lime.get("feature_contributions", {}).values()
        ]

        has_shap = len(shap_values) > 0
        has_lime = len(lime_values) > 0
        shap_all_zero = has_shap and all(abs(v) <= 1e-12 for v in shap_values)
        lime_all_zero = has_lime and all(abs(v) <= 1e-12 for v in lime_values)

        if (has_shap and shap_all_zero) or (has_lime and lime_all_zero):
            transparency_warning = (
                "All contributions are zero — model may be constant or feature mismatch detected"
            )
            logger.warning(
                "Transparency warning: all SHAP/LIME contributions are zero. "
                "Likely constant model predictions or feature mismatch between training and inference schema."
            )

            # Persist warning with artifacts so report/detail pages can surface it.
            tracker.log_dict({"warning": transparency_warning}, "transparency_warning.json")
            if sample_predictions:
                tracker.log_dict(
                    {"samples": sample_predictions, "warning": transparency_warning},
                    "sample_predictions.json",
                )
            if lime_explanations_serialized:
                tracker.log_dict(
                    {"lime_explanations": lime_explanations_serialized, "warning": transparency_warning},
                    "lime_explanations.json",
                )

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
            "sample_predictions": sample_predictions,
            "lime_explanations": lime_explanations_serialized,
            "explanation_fidelity": explanation_fidelity,
            "warning": transparency_warning,
            "mlflow_run_id": tracker._current_run.info.run_id if tracker._current_run else None
        }
        
    except Exception as e:
        # Update validation on error with rollback recovery
        try:
            await db.rollback()
            if validation is not None:
                validation.status = ValidationStatus.FAILED
                validation.error_message = _safe_error_message(e)
                validation.completed_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception as db_err:
            logger.error(f"Failed to persist transparency error state: {db_err}")
        
        try:
            if tracker is not None:
                tracker.end_validation_run(status="error", error_message=_safe_error_message(e))
        except Exception:
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
    selected_checks: Optional[list] = None,
    user_id: Optional[str] = None,
    progress_callback=None,
    # Differential Privacy parameters
    dp_target_epsilon: float = 1.0,
    dp_apply_noise: bool = False,
) -> Dict[str, Any]:
    """Core privacy validation logic (async)."""
    validation: Optional[Validation] = None
    tracker: Optional[AccountabilityTracker] = None
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
        resolved_dataset_path = _resolve_dataset_file_path(dataset_record.file_path)
        if not os.path.exists(resolved_dataset_path):
            raise FileNotFoundError(
                "Dataset file not found on disk for validation. "
                f"Stored path: '{dataset_record.file_path}', resolved path: '{resolved_dataset_path}'. "
                "Re-upload or re-load this dataset and try again."
            )
        df = pd.read_csv(resolved_dataset_path)
        
        if progress_callback:
            progress_callback(50, "Detecting PII")
        validation.progress = 50
        await db.commit()
        
        # Initialize privacy validator
        validator = PrivacyValidator(df)
        
        # Build requirements from selected checks
        checks = set(c.lower() for c in (selected_checks or ['pii_detection', 'k_anonymity', 'l_diversity']))
        requirements = {}

        if 'pii_detection' in checks:
            requirements['pii_detection'] = True

        if 'k_anonymity' in checks:
            if not quasi_identifiers:
                raise ValueError("k-anonymity selected but quasi_identifiers were not provided")
            requirements['k_anonymity'] = {
                'k': k_anonymity_k,
                'quasi_identifiers': quasi_identifiers
            }

        if 'l_diversity' in checks:
            if not quasi_identifiers:
                raise ValueError("l-diversity selected but quasi_identifiers were not provided")
            if not sensitive_attribute:
                raise ValueError("l-diversity selected but sensitive_attribute was not provided")
            requirements['l_diversity'] = {
                'l': l_diversity_l,
                'quasi_identifiers': quasi_identifiers,
                'sensitive_attribute': sensitive_attribute
            }

        if not requirements and 'differential_privacy' not in checks and 'hipaa' not in checks:
            raise ValueError("No supported privacy checks selected")
        
        if progress_callback:
            progress_callback(70, "Running privacy checks")
        validation.progress = 70
        await db.commit()
        
        # Run core validation (PII / k-anonymity / l-diversity)
        if requirements:
            report = validator.validate(requirements)
        else:
            # No core checks selected, build an empty report
            from app.validators.privacy_validator import PrivacyReport
            report = PrivacyReport(
                pii_results=[], k_anonymity=None, l_diversity=None,
                overall_passed=True, recommendations=[]
            )

        # ── Differential Privacy check (opt-in) ──────────────────────
        dp_result = None
        if 'differential_privacy' in checks:
            from app.validators.differential_privacy import DifferentialPrivacyChecker
            if not quasi_identifiers:
                raise ValueError("differential_privacy selected but quasi_identifiers were not provided")
            dp_checker = DifferentialPrivacyChecker(df)
            dp_result = dp_checker.check(
                quasi_identifiers=quasi_identifiers,
                target_epsilon=dp_target_epsilon,
                apply_noise=dp_apply_noise,
            )
            if not dp_result.budget_satisfied:
                report.overall_passed = False
                report.recommendations.append(
                    f"Differential Privacy budget EXCEEDED (ε={dp_result.measured_epsilon:.4f}, target={dp_target_epsilon}). "
                    "Consider applying Laplace noise or reducing quasi-identifier resolution."
                )
            logger.info("DP check completed: ε=%.4f satisfied=%s", dp_result.measured_epsilon, dp_result.budget_satisfied)

        # ── HIPAA Safe Harbor check (opt-in) ──────────────────────────
        hipaa_result = None
        if 'hipaa' in checks:
            from app.validators.hipaa_checker import HIPAAChecker
            hipaa_checker = HIPAAChecker(df)
            hipaa_result = hipaa_checker.check()
            if not hipaa_result.overall_passed:
                report.overall_passed = False
                failed_ids = [r.label for r in hipaa_result.results if not r.passed]
                report.recommendations.append(
                    f"HIPAA Safe Harbor check FAILED for: {', '.join(failed_ids)}. "
                    "Remove or de-identify flagged columns before deployment."
                )
            logger.info("HIPAA check completed: %d/%d passed", hipaa_result.passed_checks, hipaa_result.total_checks)
        
        # Log to MLflow
        metrics = {
            "pii_detected_count": len([r for r in report.pii_results if r.is_pii]),
            "overall_passed": 1.0 if report.overall_passed else 0.0
        }
        if report.k_anonymity:
            metrics["k_anonymity_satisfied"] = 1.0 if report.k_anonymity.satisfies_k else 0.0
        if report.l_diversity:
            metrics["l_diversity_satisfied"] = 1.0 if report.l_diversity.satisfies_l else 0.0
        if dp_result:
            metrics["dp_measured_epsilon"] = dp_result.measured_epsilon
            metrics["dp_budget_satisfied"] = 1.0 if dp_result.budget_satisfied else 0.0
        if hipaa_result:
            metrics["hipaa_passed"] = 1.0 if hipaa_result.overall_passed else 0.0
            metrics["hipaa_checks_passed"] = float(hipaa_result.passed_checks)
        
        # Calculate dynamic privacy risk score
        total_checks = 0
        failed_checks = 0
        
        # Count PII detection
        if 'pii_detection' in checks:
            total_checks += 1
            pii_count = len([r for r in report.pii_results if r.is_pii])
            if pii_count > 0:
                failed_checks += 1
        
        # Count k-anonymity
        if report.k_anonymity:
            total_checks += 1
            if not report.k_anonymity.satisfies_k:
                failed_checks += 1
            # Additional risk for very low k values
            if report.k_anonymity.actual_min_k < 3:
                failed_checks += 0.5  # Partial failure for low k
        
        # Count l-diversity
        if report.l_diversity:
            total_checks += 1
            if not report.l_diversity.satisfies_l:
                failed_checks += 1
        
        # Count differential privacy
        if dp_result:
            total_checks += 1
            if not dp_result.budget_satisfied:
                failed_checks += 1
        
        # Count HIPAA
        if hipaa_result:
            total_checks += 1
            if not hipaa_result.overall_passed:
                failed_checks += 1
        
        # Calculate risk score: 0% = no risk, 100% = all checks failed
        if total_checks > 0:
            privacy_risk_score = min(100, int((failed_checks / total_checks) * 100))
        else:
            privacy_risk_score = 0
        
        metrics["privacy_risk_score"] = float(privacy_risk_score)
        
        report_dict = report.to_dict()
        if dp_result:
            report_dict["differential_privacy"] = dp_result.to_dict()
        if hipaa_result:
            report_dict["hipaa"] = hipaa_result.to_dict()
        # Add privacy_risk_score to the artifact for frontend consumption
        report_dict["privacy_risk_score"] = privacy_risk_score

        tracker.log_metrics(metrics)
        tracker.log_dict(report_dict, "privacy_report.json")
        
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
            "differential_privacy": dp_result.to_dict() if dp_result else None,
            "hipaa": hipaa_result.to_dict() if hipaa_result else None,
            "privacy_risk_score": privacy_risk_score,
            "recommendations": report.recommendations,
            "mlflow_run_id": tracker._current_run.info.run_id if tracker._current_run else None
        }
        
    except Exception as e:
        # Update validation on error with rollback recovery
        try:
            await db.rollback()
            if validation is not None:
                validation.status = ValidationStatus.FAILED
                validation.error_message = _safe_error_message(e)
                validation.completed_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception as db_err:
            logger.error(f"Failed to persist privacy error state: {db_err}")
        
        try:
            if tracker is not None:
                tracker.end_validation_run(status="error", error_message=_safe_error_message(e))
        except Exception:
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
    
    return _run_async_in_task_loop(_run())


@celery_app.task(bind=True, name="run_privacy_validation_task")
def run_privacy_validation_task(
    self,
    validation_id: str,
    dataset_id: str,
    k_anonymity_k: int = 5,
    l_diversity_l: int = 2,
    quasi_identifiers: Optional[list] = None,
    sensitive_attribute: Optional[str] = None,
    selected_checks: Optional[list] = None,
    user_id: Optional[str] = None,
    dp_target_epsilon: float = 1.0,
    dp_apply_noise: bool = False,
) -> Dict[str, Any]:
    """Run privacy validation in background."""
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
                selected_checks=selected_checks,
                user_id=user_id,
                progress_callback=progress_callback,
                dp_target_epsilon=dp_target_epsilon,
                dp_apply_noise=dp_apply_noise,
            )
    
    return _run_async_in_task_loop(_run())


@celery_app.task(bind=True, name="run_all_validations_task")
def run_all_validations_task(
    self,
    suite_id: str,
    model_id: str,
    dataset_id: str,
    fairness_config: Dict[str, Any],
    transparency_config: Dict[str, Any],
    privacy_config: Dict[str, Any],
    user_id: Optional[str] = None,
    selected_validations: Optional[list] = None,
    requirement_ids: Optional[list] = None
) -> Dict[str, Any]:
    """
    Run selected validations in sequence.

    selected_validations is a list of zero or more of:
        "fairness", "transparency", "privacy", "accountability"
    If empty / None every validator runs (backward-compatible default).
    """
    from app.models.validation_suite import ValidationSuite

    # ── normalise selection ────────────────────────────────────────────
    ALL = ["fairness", "transparency", "privacy", "accountability"]
    if not selected_validations:
        run_set = set(ALL)
    else:
        run_set = set(v.lower() for v in selected_validations)

    # validators that produce DB records (accountability is handled separately)
    db_validators = [v for v in ["fairness", "transparency", "privacy"] if v in run_set]
    run_accountability = "accountability" in run_set

    # ── progress slices ───────────────────────────────────────────────
    # Split 0-95% equally among the DB validators (+ 1 slice if accountability only)
    slice_count = len(db_validators) + (1 if run_accountability and not db_validators else 0)
    slice_size = int(95 / slice_count) if slice_count else 95

    def start_pct(validator_index):
        return validator_index * slice_size

    async def _run():
        suite = None
        async with async_session_maker() as db:
            try:
                result = await db.execute(
                    select(ValidationSuite).where(ValidationSuite.id == UUID(suite_id))
                )
                suite = result.scalar_one()

                # Build a mapping from principle → requirement_id for linking
                principle_to_requirement_id: Dict[str, UUID] = {}
                if requirement_ids:
                    from app.models.requirement import Requirement
                    for rid_str in requirement_ids:
                        req_result = await db.execute(
                            select(Requirement).where(Requirement.id == UUID(rid_str))
                        )
                        req_obj = req_result.scalar_one_or_none()
                        if req_obj:
                            principle_to_requirement_id[req_obj.principle] = req_obj.id

                results = {
                    "suite_id": suite_id,
                    "validations": {}
                }

                idx = 0  # tracks which slice we're in

                # ── 1. Fairness ───────────────────────────────────────
                if "fairness" in run_set:
                    base = start_pct(idx)
                    self.update_state(state="PROGRESS", meta={"progress": base, "step": "Starting fairness validation"})

                    fairness_validation = Validation(
                        model_id=UUID(model_id),
                        dataset_id=UUID(dataset_id),
                        requirement_id=principle_to_requirement_id.get("fairness"),
                        status=ValidationStatus.PENDING,
                        progress=0
                    )
                    db.add(fairness_validation)
                    await db.commit()
                    await db.refresh(fairness_validation)

                    fairness_result = await _run_fairness_validation_async(
                        db=db,
                        validation_id=str(fairness_validation.id),
                        model_id=model_id,
                        dataset_id=dataset_id,
                        user_id=user_id,
                        progress_callback=lambda p, s: self.update_state(
                            state="PROGRESS",
                            meta={"progress": base + int(p * slice_size / 100), "step": f"Fairness: {s}"}
                        ),
                        **fairness_config
                    )

                    if fairness_result.get("mlflow_run_id"):
                        fairness_validation.mlflow_run_id = fairness_result["mlflow_run_id"]
                        await db.commit()

                    results["validations"]["fairness"] = fairness_result
                    suite.fairness_validation_id = fairness_validation.id
                    await db.commit()
                    idx += 1

                # ── 2. Transparency ───────────────────────────────────
                if "transparency" in run_set:
                    base = start_pct(idx)
                    self.update_state(state="PROGRESS", meta={"progress": base, "step": "Starting transparency validation"})

                    transparency_validation = Validation(
                        model_id=UUID(model_id),
                        dataset_id=UUID(dataset_id),
                        requirement_id=principle_to_requirement_id.get("transparency"),
                        status=ValidationStatus.PENDING,
                        progress=0
                    )
                    db.add(transparency_validation)
                    await db.commit()
                    await db.refresh(transparency_validation)

                    transparency_result = await _run_transparency_validation_async(
                        db=db,
                        validation_id=str(transparency_validation.id),
                        model_id=model_id,
                        dataset_id=dataset_id,
                        user_id=user_id,
                        progress_callback=lambda p, s: self.update_state(
                            state="PROGRESS",
                            meta={"progress": base + int(p * slice_size / 100), "step": f"Transparency: {s}"}
                        ),
                        **transparency_config
                    )

                    if transparency_result.get("mlflow_run_id"):
                        transparency_validation.mlflow_run_id = transparency_result["mlflow_run_id"]
                        await db.commit()

                    results["validations"]["transparency"] = transparency_result
                    suite.transparency_validation_id = transparency_validation.id
                    await db.commit()
                    idx += 1

                # ── 3. Privacy ────────────────────────────────────────
                if "privacy" in run_set:
                    base = start_pct(idx)
                    self.update_state(state="PROGRESS", meta={"progress": base, "step": "Starting privacy validation"})

                    privacy_validation = Validation(
                        model_id=UUID(model_id) if model_id else None,
                        dataset_id=UUID(dataset_id),
                        requirement_id=principle_to_requirement_id.get("privacy"),
                        status=ValidationStatus.PENDING,
                        progress=0
                    )
                    db.add(privacy_validation)
                    await db.commit()
                    await db.refresh(privacy_validation)

                    privacy_result = await _run_privacy_validation_async(
                        db=db,
                        validation_id=str(privacy_validation.id),
                        dataset_id=dataset_id,
                        user_id=user_id,
                        progress_callback=lambda p, s: self.update_state(
                            state="PROGRESS",
                            meta={"progress": base + int(p * slice_size / 100), "step": f"Privacy: {s}"}
                        ),
                        **privacy_config
                    )

                    if privacy_result.get("mlflow_run_id"):
                        privacy_validation.mlflow_run_id = privacy_result["mlflow_run_id"]
                        await db.commit()

                    results["validations"]["privacy"] = privacy_result
                    suite.privacy_validation_id = privacy_validation.id
                    await db.commit()
                    idx += 1

                # ── 4. Accountability (standalone audit summary) ──────
                if run_accountability and not db_validators:
                    # Accountability-only run: emit a simple audit record
                    base = start_pct(0)
                    self.update_state(state="PROGRESS", meta={"progress": base, "step": "Recording accountability audit"})
                    tracker = AccountabilityTracker(
                        tracking_uri=settings.mlflow_tracking_uri,
                        experiment_name=settings.mlflow_experiment_name,
                        use_mlflow=True
                    )
                    run_id = tracker.start_validation_run(
                        model_name=model_id,
                        model_id=model_id,
                        dataset_name=dataset_id,
                        dataset_id=dataset_id,
                        requirement_name="Accountability Audit",
                        requirement_id=suite_id,
                        principle="accountability",
                        user_id=user_id
                    )
                    tracker.log_metrics({"audit_generated": 1})
                    tracker.end_validation_run(status="completed")
                    results["validations"]["accountability"] = {
                        "status": "completed",
                        "progress": 100,
                        "mlflow_run_id": run_id,
                        "message": "Audit trail recorded via MLflow"
                    }
                elif run_accountability:
                    # Accountability is implicitly tracked inside each validator run
                    results["validations"]["accountability"] = {
                        "status": "completed",
                        "progress": 100,
                        "message": "Audit trail recorded alongside selected validations"
                    }

                # ── Finalise ──────────────────────────────────────────
                self.update_state(state="PROGRESS", meta={"progress": 95, "step": "Finalizing results"})

                fairness_passed  = results["validations"].get("fairness", {}).get("overall_passed", True)
                transp_passed    = results["validations"].get("transparency", {}).get("status") in (None, "completed", "skipped")
                privacy_passed   = results["validations"].get("privacy", {}).get("overall_passed", True)
                overall_passed   = fairness_passed and transp_passed and privacy_passed

                suite.status = "completed"
                suite.overall_passed = overall_passed
                suite.completed_at = datetime.now(timezone.utc)
                await db.commit()

                results["overall_passed"] = overall_passed
                results["status"] = "completed"

                self.update_state(state="PROGRESS", meta={"progress": 100, "step": "Complete"})
                return results

            except Exception as e:
                logger.error(f"Validation suite failed: {str(e)}")
                if suite is not None:
                    try:
                        await db.rollback()
                        suite.status = "failed"
                        suite.error_message = _safe_error_message(e)
                        suite.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                    except Exception as db_err:
                        logger.error(f"Failed to persist suite error state: {db_err}")
                raise

    return _run_async_in_task_loop(_run())
