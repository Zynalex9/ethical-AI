"""
Accountability Tracker - MLflow integration and audit trail management.

Implements:
- MLflow experiment tracking for validation runs
- Model versioning and lineage tracking
- Audit log management
- Requirement traceability

Reference: Supports regulatory compliance by maintaining complete
audit trails of all validation activities.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class ValidationRecord:
    """Record of a validation run for audit purposes."""
    validation_id: str
    model_id: str
    model_name: str
    dataset_id: str
    dataset_name: str
    requirement_id: str
    requirement_name: str
    principle: str  # fairness, transparency, privacy, accountability
    status: str  # passed, failed, error
    metrics: Dict[str, Any]
    timestamp: datetime
    user_id: Optional[str] = None
    mlflow_run_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "requirement_id": self.requirement_id,
            "requirement_name": self.requirement_name,
            "principle": self.principle,
            "status": self.status,
            "metrics": self.metrics,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "mlflow_run_id": self.mlflow_run_id
        }


@dataclass
class ModelVersion:
    """Track model versions for lineage."""
    model_id: str
    version: str
    model_path: str
    model_type: str
    created_at: datetime
    created_by: Optional[str]
    metadata: Dict[str, Any]
    validation_history: List[str] = field(default_factory=list)  # validation_ids
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "model_path": self.model_path,
            "model_type": self.model_type,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
            "validation_count": len(self.validation_history)
        }


class AccountabilityTracker:
    """
    Tracks validation activities for audit and accountability.
    
    Integrates with MLflow for experiment tracking and provides
    a complete trail of model validations.
    
    Usage:
        tracker = AccountabilityTracker(
            tracking_uri="sqlite:///mlflow.db",
            experiment_name="ethical-ai-validations"
        )
        
        # Start tracking a validation
        run_id = tracker.start_validation_run(
            model_name="loan_model_v3",
            requirement_name="ETH1-Fairness"
        )
        
        # Log metrics
        tracker.log_metrics({
            "demographic_parity_ratio": 0.85,
            "equalized_odds_ratio": 0.78
        })
        
        # End run
        tracker.end_validation_run(status="passed")
    """
    
    def __init__(
        self,
        tracking_uri: str = "sqlite:///mlflow.db",
        experiment_name: str = "ethical-ai-validations",
        use_mlflow: bool = True
    ):
        """
        Initialize accountability tracker.
        
        Args:
            tracking_uri: MLflow tracking URI
            experiment_name: Name of MLflow experiment
            use_mlflow: Whether to enable MLflow tracking
        """
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.use_mlflow = use_mlflow
        self._mlflow = None
        self._current_run = None
        self._experiment_id = None
        
        # In-memory storage for demo (use database in production)
        self._validation_records: List[ValidationRecord] = []
        self._model_versions: Dict[str, ModelVersion] = {}
        
        if use_mlflow:
            self._init_mlflow()
    
    def _init_mlflow(self) -> None:
        """Initialize MLflow tracking."""
        try:
            import mlflow
            self._mlflow = mlflow
            
            # Set tracking URI
            mlflow.set_tracking_uri(self.tracking_uri)
            
            # Create or get experiment
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if experiment is None:
                self._experiment_id = mlflow.create_experiment(self.experiment_name)
            else:
                self._experiment_id = experiment.experiment_id
            
            mlflow.set_experiment(self.experiment_name)
            
            logger.info(f"MLflow initialized with experiment '{self.experiment_name}'")
            
        except ImportError:
            logger.warning("MLflow not installed. Running without experiment tracking.")
            self.use_mlflow = False
    
    def start_validation_run(
        self,
        model_name: str,
        model_id: str,
        dataset_name: str,
        dataset_id: str,
        requirement_name: str,
        requirement_id: str,
        principle: str,
        user_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Start tracking a new validation run.
        
        Args:
            model_name: Name of the model being validated
            model_id: Unique model identifier
            dataset_name: Name of the test dataset
            dataset_id: Unique dataset identifier
            requirement_name: Name of the requirement
            requirement_id: Unique requirement identifier
            principle: Ethical principle (fairness, transparency, privacy, accountability)
            user_id: ID of user running validation
            tags: Additional tags for the run
            
        Returns:
            Run ID (MLflow run_id if enabled, else generated UUID)
        """
        import uuid
        
        run_id = str(uuid.uuid4())
        
        if self.use_mlflow and self._mlflow:
            # Start MLflow run
            run = self._mlflow.start_run(
                run_name=f"{requirement_name}_{model_name}",
                tags={
                    "model_name": model_name,
                    "model_id": model_id,
                    "dataset_name": dataset_name,
                    "dataset_id": dataset_id,
                    "requirement_name": requirement_name,
                    "requirement_id": requirement_id,
                    "principle": principle,
                    "user_id": user_id or "unknown",
                    **(tags or {})
                }
            )
            self._current_run = run
            run_id = run.info.run_id
            
            # Log parameters
            self._mlflow.log_param("model_name", model_name)
            self._mlflow.log_param("model_id", model_id)
            self._mlflow.log_param("dataset_name", dataset_name)
            self._mlflow.log_param("requirement_name", requirement_name)
            self._mlflow.log_param("principle", principle)
        
        # Store run context
        self._current_run_context = {
            "run_id": run_id,
            "model_name": model_name,
            "model_id": model_id,
            "dataset_name": dataset_name,
            "dataset_id": dataset_id,
            "requirement_name": requirement_name,
            "requirement_id": requirement_id,
            "principle": principle,
            "user_id": user_id,
            "start_time": datetime.now(timezone.utc),
            "metrics": {}
        }
        
        logger.info(f"Started validation run {run_id} for {model_name} / {requirement_name}")
        
        return run_id
    
    def log_metrics(self, metrics: Dict[str, float]) -> None:
        """
        Log metrics for the current validation run.
        
        Args:
            metrics: Dictionary of metric name -> value
        """
        if not hasattr(self, '_current_run_context'):
            logger.warning("No active validation run context, creating empty one")
            self._current_run_context = {"metrics": {}, "params": {}, "artifacts": []}
        
        # Store metrics
        self._current_run_context["metrics"].update(metrics)
        
        # Log to MLflow
        if self.use_mlflow and self._mlflow and self._current_run:
            for name, value in metrics.items():
                if isinstance(value, (int, float)):
                    try:
                        # Sanitize metric name for MLflow (no spaces, special chars)
                        safe_name = str(name).replace(" ", "_").replace("-", "_").replace(".", "_")
                        safe_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in safe_name)
                        self._mlflow.log_metric(safe_name, float(value))
                    except Exception as e:
                        logger.warning(f"Failed to log metric '{name}': {str(e)}")
        
        logger.debug(f"Logged {len(metrics)} metrics")
    
    def log_artifact(self, file_path: str, artifact_path: Optional[str] = None) -> None:
        """
        Log an artifact (file) for the current run.
        
        Args:
            file_path: Local path to the file
            artifact_path: Optional subdirectory in artifact store
        """
        if self.use_mlflow and self._mlflow and self._current_run:
            self._mlflow.log_artifact(file_path, artifact_path)
            logger.debug(f"Logged artifact: {file_path}")
    
    def log_dict(self, data: Dict[str, Any], filename: str) -> None:
        """
        Log a dictionary as JSON artifact.
        
        Args:
            data: Dictionary to log
            filename: Name for the JSON file
        """
        # FIX: Complete rewrite with better error handling and debugging
        if not self.use_mlflow:
            logger.warning(f"❌ MLflow disabled, cannot save {filename}")
            raise RuntimeError(f"MLflow disabled, cannot save {filename}")
            
        if not self._mlflow:
            logger.error(f"❌ MLflow client not initialized, cannot save {filename}")
            raise RuntimeError(f"MLflow client not initialized, cannot save {filename}")
            
        if not self._current_run:
            logger.error(f"❌ No active MLflow run, cannot save {filename}")
            raise RuntimeError(f"No active MLflow run, cannot save {filename}")
        
        try:
            run_id = self._current_run.info.run_id
            logger.info(f"🔄 Attempting to save {filename} to run {run_id}...")
            
            # Use mlflow.log_dict which saves as JSON artifact
            self._mlflow.log_dict(data, filename)
            
            # Verify the file was actually saved
            import os
            artifact_uri = self._current_run.info.artifact_uri
            
            # FIX: Properly convert artifact URI to Windows path
            if artifact_uri.startswith("file:///"):
                # Remove file:/// prefix and convert forward slashes to backslashes
                local_path = artifact_uri.replace("file:///", "").replace("/", "\\")
            elif artifact_uri.startswith("file://"):
                # Remove file:// prefix and convert
                local_path = artifact_uri.replace("file://", "").replace("/", "\\")
            elif artifact_uri.startswith("./"):
                # Relative path - make absolute
                local_path = os.path.abspath(artifact_uri)
            else:
                local_path = artifact_uri.replace("/", "\\")
            
            # Build full path to artifact file
            expected_path = os.path.join(local_path, filename)
            
            if os.path.exists(expected_path):
                file_size = os.path.getsize(expected_path)
                logger.info(f"✅ SUCCESS: Saved {filename} ({file_size} bytes) to {expected_path}")
            else:
                logger.warning(f"⚠️ File saved but not found at expected path: {expected_path}")
                # Try to find where it actually went
                artifact_dir = os.path.dirname(expected_path)
                if os.path.exists(artifact_dir):
                    files = os.listdir(artifact_dir)
                    logger.info(f"📁 Files in artifact dir: {files}")
                else:
                    logger.error(f"❌ Artifact directory doesn't exist: {artifact_dir}")
                
        except Exception as e:
            logger.error(f"❌ FAILED to save {filename}: {str(e)}", exc_info=True)
            # Re-raise so caller can handle it
            raise
    
    def end_validation_run(
        self,
        status: str = "completed",
        error_message: Optional[str] = None
    ) -> ValidationRecord:
        """
        End the current validation run and record results.
        
        Args:
            status: Run status ("passed", "failed", "error")
            error_message: Error details if status is "error"
            
        Returns:
            ValidationRecord for the completed run
        """
        if not hasattr(self, '_current_run_context'):
            raise RuntimeError("No active validation run to end.")
        
        ctx = self._current_run_context
        
        # Log status
        if self.use_mlflow and self._mlflow and self._current_run:
            self._mlflow.set_tag("status", status)
            if error_message:
                self._mlflow.set_tag("error_message", error_message)
            self._mlflow.end_run()
        
        # Create validation record
        record = ValidationRecord(
            validation_id=ctx["run_id"],
            model_id=ctx["model_id"],
            model_name=ctx["model_name"],
            dataset_id=ctx["dataset_id"],
            dataset_name=ctx["dataset_name"],
            requirement_id=ctx["requirement_id"],
            requirement_name=ctx["requirement_name"],
            principle=ctx["principle"],
            status=status,
            metrics=ctx["metrics"],
            timestamp=ctx["start_time"],
            user_id=ctx["user_id"],
            mlflow_run_id=ctx["run_id"] if self.use_mlflow else None
        )
        
        self._validation_records.append(record)
        
        # Update model version validation history
        if ctx["model_id"] in self._model_versions:
            self._model_versions[ctx["model_id"]].validation_history.append(ctx["run_id"])
        
        # Clean up
        self._current_run = None
        delattr(self, '_current_run_context')
        
        logger.info(f"Ended validation run {record.validation_id} with status: {status}")
        
        return record
    
    def register_model_version(
        self,
        model_id: str,
        version: str,
        model_path: str,
        model_type: str,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ModelVersion:
        """
        Register a model version for tracking.
        
        Args:
            model_id: Unique model identifier
            version: Version string (e.g., "1.0.0", "v3")
            model_path: Path to model file
            model_type: Model type (sklearn, tensorflow, etc.)
            created_by: User who created this version
            metadata: Additional model metadata
            
        Returns:
            ModelVersion record
        """
        model_version = ModelVersion(
            model_id=model_id,
            version=version,
            model_path=model_path,
            model_type=model_type,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            metadata=metadata or {}
        )
        
        self._model_versions[model_id] = model_version
        
        # Log to MLflow model registry if available
        if self.use_mlflow and self._mlflow:
            try:
                # Note: Full model registry requires MLflow Pro or self-hosted MLflow
                logger.info(f"Registered model version {model_id} v{version}")
            except Exception as e:
                logger.warning(f"Could not register with MLflow: {e}")
        
        return model_version
    
    def get_validation_history(
        self,
        model_id: Optional[str] = None,
        requirement_id: Optional[str] = None,
        principle: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[ValidationRecord]:
        """
        Query validation history with filters.
        
        Args:
            model_id: Filter by model
            requirement_id: Filter by requirement
            principle: Filter by ethical principle
            status: Filter by status (passed/failed/error)
            limit: Maximum records to return
            
        Returns:
            List of matching ValidationRecords
        """
        results = self._validation_records
        
        if model_id:
            results = [r for r in results if r.model_id == model_id]
        if requirement_id:
            results = [r for r in results if r.requirement_id == requirement_id]
        if principle:
            results = [r for r in results if r.principle == principle]
        if status:
            results = [r for r in results if r.status == status]
        
        # Sort by timestamp descending
        results = sorted(results, key=lambda x: x.timestamp, reverse=True)
        
        return results[:limit]
    
    def get_model_lineage(self, model_id: str) -> Dict[str, Any]:
        """
        Get complete lineage for a model including all validations.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Dictionary with model info and validation history
        """
        model = self._model_versions.get(model_id)
        if not model:
            return {"error": f"Model {model_id} not found"}
        
        validations = self.get_validation_history(model_id=model_id)
        
        return {
            "model": model.to_dict(),
            "validations": [v.to_dict() for v in validations],
            "summary": {
                "total_validations": len(validations),
                "passed": len([v for v in validations if v.status == "passed"]),
                "failed": len([v for v in validations if v.status == "failed"]),
                "principles_validated": list(set(v.principle for v in validations))
            }
        }
    
    def generate_audit_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive audit report.
        
        Args:
            start_date: Filter from date
            end_date: Filter to date
            
        Returns:
            Audit report dictionary
        """
        records = self._validation_records
        
        # Filter by date range
        if start_date:
            records = [r for r in records if r.timestamp >= start_date]
        if end_date:
            records = [r for r in records if r.timestamp <= end_date]
        
        # Generate statistics
        total = len(records)
        by_status = {}
        by_principle = {}
        by_model = {}
        
        for r in records:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_principle[r.principle] = by_principle.get(r.principle, 0) + 1
            by_model[r.model_name] = by_model.get(r.model_name, 0) + 1
        
        return {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "period": {
                "start": start_date.isoformat() if start_date else "all",
                "end": end_date.isoformat() if end_date else "all"
            },
            "summary": {
                "total_validations": total,
                "by_status": by_status,
                "by_principle": by_principle,
                "models_validated": len(by_model),
                "pass_rate": by_status.get("passed", 0) / total if total > 0 else 0
            },
            "model_statistics": by_model,
            "recent_validations": [r.to_dict() for r in records[:10]]
        }
    
    def export_audit_trail(self, filepath: str) -> None:
        """
        Export complete audit trail to JSON file.
        
        Args:
            filepath: Path to save JSON file
        """
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "validation_records": [r.to_dict() for r in self._validation_records],
            "model_versions": {k: v.to_dict() for k, v in self._model_versions.items()}
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported audit trail to {filepath}")
