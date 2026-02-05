"""
Benchmark Dataset Seeding Service.

This service loads pre-configured benchmark datasets (COMPAS, Adult Income, German Credit)
into projects with proper metadata and sensitive attribute configuration.
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from uuid import UUID
import logging

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.dataset import Dataset
from app.models.project import Project
from app.models.audit_log import AuditLog, AuditAction, ResourceType

logger = logging.getLogger(__name__)


class BenchmarkDatasetSeeder:
    """
    Service for loading benchmark datasets into projects.
    
    Provides one-click loading of pre-configured benchmark datasets
    with automatic sensitive attribute detection and metadata.
    """
    
    # Dataset metadata configuration
    BENCHMARK_DATASETS = {
        "compas": {
            "name": "COMPAS Recidivism",
            "description": "Criminal recidivism risk assessment dataset from Broward County, Florida. Used to study racial bias in algorithmic risk assessment tools.",
            "filename": "compas-scores-raw.csv",
            "target_column": "two_year_recid",
            "sensitive_attributes": ["race", "sex", "age_cat"],
            "key_features": ["age", "priors_count", "c_charge_degree", "decile_score"],
            "domain": "criminal_justice",
            "reference": "ProPublica COMPAS Analysis (2016)"
        },
        "adult_income": {
            "name": "Adult Income (Census)",
            "description": "Census data from 1994 used to predict whether income exceeds $50K/year. Widely used for fairness research.",
            "filename": "adult.csv",
            "target_column": "income",
            "sensitive_attributes": ["sex", "race", "native-country"],
            "key_features": ["age", "education", "occupation", "hours-per-week", "marital-status"],
            "domain": "employment",
            "reference": "UCI Machine Learning Repository"
        },
        "german_credit": {
            "name": "German Credit",
            "description": "Credit risk assessment dataset from a German bank. Used for fairness in lending and ECOA compliance studies.",
            "filename": "german_credit_data.csv",
            "target_column": "credit_risk",
            "sensitive_attributes": ["sex", "age", "foreign_worker"],
            "key_features": ["duration", "credit_amount", "installment_rate", "property", "existing_credits"],
            "domain": "finance",
            "reference": "UCI Machine Learning Repository - Statlog German Credit"
        }
    }
    
    def __init__(self):
        """Initialize the seeder with benchmark dataset path."""
        # Get the path to benchmark datasets
        current_file = Path(__file__)
        self.benchmark_dir = current_file.parent.parent / "datasets" / "benchmark"
        
        if not self.benchmark_dir.exists():
            raise FileNotFoundError(
                f"Benchmark dataset directory not found: {self.benchmark_dir}"
            )
    
    async def seed_benchmark_datasets(
        self,
        project_id: UUID,
        dataset_key: str,
        db: AsyncSession,
        user_id: UUID
    ) -> Dataset:
        """
        Load a single benchmark dataset into a project.
        
        Args:
            project_id: Target project UUID
            dataset_key: Key identifying the benchmark dataset ("compas", "adult_income", "german_credit")
            db: Database session
            user_id: User performing the operation
            
        Returns:
            Created Dataset model instance
            
        Raises:
            ValueError: If dataset_key is invalid
            FileNotFoundError: If dataset file doesn't exist
        """
        # Validate dataset key
        if dataset_key not in self.BENCHMARK_DATASETS:
            raise ValueError(
                f"Invalid dataset key: {dataset_key}. "
                f"Valid options: {list(self.BENCHMARK_DATASETS.keys())}"
            )
        
        # Get dataset metadata
        metadata = self.BENCHMARK_DATASETS[dataset_key]
        
        # Verify project exists
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None)
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        # Load and profile the dataset
        source_path = self.benchmark_dir / metadata["filename"]
        if not source_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {source_path}")
        
        # Read dataset to get profiling information
        df = pd.read_csv(source_path)
        
        # Create upload directory for this project
        upload_dir = Path("uploads") / "datasets" / str(project_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy file to uploads directory
        dest_filename = f"{dataset_key}_{metadata['filename']}"
        dest_path = upload_dir / dest_filename
        shutil.copy2(source_path, dest_path)
        
        # Profile the dataset
        profile_data = self._profile_dataset(df)
        
        # Create dataset record
        dataset = Dataset(
            project_id=project_id,
            name=metadata["name"],
            description=metadata["description"],
            file_path=str(dest_path),
            row_count=len(df),
            column_count=len(df.columns),
            columns=df.columns.tolist(),
            sensitive_attributes=metadata["sensitive_attributes"],
            target_column=metadata["target_column"],
            profile_data=profile_data,
            uploaded_by_id=user_id
        )
        
        db.add(dataset)
        
        # Create audit log
        # FIX: Changed AuditAction.CREATE to DATASET_UPLOAD (correct enum value)
        audit_log = AuditLog(
            user_id=user_id,
            action=AuditAction.DATASET_UPLOAD,
            resource_type=ResourceType.DATASET,
            resource_id=dataset.id,
            details={
                "dataset_name": metadata["name"],
                "dataset_key": dataset_key,
                "domain": metadata["domain"],
                "reference": metadata["reference"],
                "is_benchmark": True
            }
        )
        db.add(audit_log)
        
        await db.commit()
        await db.refresh(dataset)
        
        logger.info(
            f"Loaded benchmark dataset '{dataset_key}' into project {project_id}. "
            f"Dataset ID: {dataset.id}, Rows: {dataset.row_count}"
        )
        
        return dataset
    
    async def seed_all_datasets(
        self,
        project_id: UUID,
        db: AsyncSession,
        user_id: UUID
    ) -> List[Dataset]:
        """
        Load all benchmark datasets into a project.
        
        Args:
            project_id: Target project UUID
            db: Database session
            user_id: User performing the operation
            
        Returns:
            List of created Dataset model instances
        """
        datasets = []
        
        for dataset_key in self.BENCHMARK_DATASETS.keys():
            try:
                dataset = await self.seed_benchmark_datasets(
                    project_id=project_id,
                    dataset_key=dataset_key,
                    db=db,
                    user_id=user_id
                )
                datasets.append(dataset)
            except Exception as e:
                logger.error(f"Failed to load dataset '{dataset_key}': {str(e)}")
                # Continue with other datasets even if one fails
                continue
        
        return datasets
    
    def get_available_datasets(self) -> Dict[str, Dict]:
        """
        Get metadata for all available benchmark datasets.
        
        Returns:
            Dictionary mapping dataset keys to metadata
        """
        return self.BENCHMARK_DATASETS.copy()
    
    def _profile_dataset(self, df: pd.DataFrame) -> Dict:
        """
        Generate profiling data for a dataset.
        
        Args:
            df: Pandas DataFrame
            
        Returns:
            Dictionary containing profiling information
        """
        profile = {
            "column_types": {},
            "missing_values": {},
            "unique_counts": {},
            "value_counts": {}
        }
        
        for col in df.columns:
            # Data type
            profile["column_types"][col] = str(df[col].dtype)
            
            # Missing values
            missing_count = int(df[col].isna().sum())
            profile["missing_values"][col] = missing_count
            
            # Unique values
            unique_count = int(df[col].nunique())
            profile["unique_counts"][col] = unique_count
            
            # For categorical columns with few unique values, store value counts
            if unique_count <= 20:
                value_counts = df[col].value_counts().head(20).to_dict()
                # Convert keys and values to native Python types
                profile["value_counts"][col] = {
                    str(k): int(v) for k, v in value_counts.items()
                }
        
        return profile
