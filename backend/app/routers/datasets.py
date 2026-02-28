# Datasets router - Dataset upload and management

import os
import shutil
import logging
from typing import List, Optional
from uuid import UUID
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pandas as pd

from ..database import get_db
from ..dependencies import get_current_user
from ..config import settings
from ..models.user import User
from ..models.project import Project
from ..models.dataset import Dataset
from ..models.audit_log import AuditLog, AuditAction, ResourceType

# FIX: Added logger initialization to handle error logging in load_benchmark_dataset
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])
ALLOWED_DATASET_EXTENSIONS = {".csv"}


# Pydantic models for responses
from pydantic import BaseModel

class DatasetResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    file_path: str
    row_count: int
    column_count: int
    columns: List[str]
    sensitive_attributes: List[str]
    target_column: Optional[str]
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class DatasetProfileResponse(BaseModel):
    id: UUID
    name: str
    row_count: int
    column_count: int
    columns: List[str]
    column_types: dict
    missing_values: dict
    unique_counts: dict
    sample_data: List[dict]


@router.post("/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    project_id: UUID = Form(...),
    description: Optional[str] = Form(None),
    sensitive_attributes: Optional[str] = Form(None),  # Comma-separated
    target_column: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a dataset file (CSV format).
    
    Args:
        file: CSV file to upload
        name: Display name for the dataset
        project_id: Project to associate with
        sensitive_attributes: Comma-separated list of sensitive columns (e.g., "gender,race")
        target_column: Name of the target/label column
    """
    # Verify project exists and user has access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_DATASET_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_DATASET_EXTENSIONS))}"
        )

    if not name.strip():
        raise HTTPException(status_code=400, detail="Dataset name cannot be empty")
    
    # Create upload directory
    upload_dir = Path(settings.upload_dir) / "datasets" / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-").strip("._-")
    if not safe_name:
        safe_name = "dataset"
    filename = f"{safe_name}_{timestamp}{ext}"
    file_path = upload_dir / filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Parse CSV and extract metadata
    try:
        file_size = os.path.getsize(file_path)
        if file_size <= 0:
            raise HTTPException(status_code=400, detail="Uploaded dataset file is empty")

        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Dataset file exceeds maximum size of {settings.max_upload_size_mb} MB"
            )

        df = pd.read_csv(file_path)
        row_count = len(df)
        column_count = len(df.columns)
        columns = df.columns.tolist()

        if row_count == 0:
            raise HTTPException(status_code=400, detail="Dataset has no rows")
        if column_count == 0:
            raise HTTPException(status_code=400, detail="Dataset has no columns")
        
        # Generate profile data
        profile_data = {
            "column_types": {col: str(df[col].dtype) for col in columns},
            "missing_values": df.isnull().sum().to_dict(),
            "unique_counts": {col: int(df[col].nunique()) for col in columns},
            "memory_usage": int(df.memory_usage(deep=True).sum())
        }
    except HTTPException:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    
    # Parse sensitive attributes
    sensitive_list = []
    if sensitive_attributes:
        sensitive_list = [s.strip() for s in sensitive_attributes.split(",") if s.strip()]
        # Validate columns exist
        invalid = set(sensitive_list) - set(columns)
        if invalid:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"Sensitive columns not found in dataset: {invalid}"
            )
    
    # Validate target column
    if target_column and target_column not in columns:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Target column '{target_column}' not found in dataset"
        )
    
    # Create database record
    dataset = Dataset(
        project_id=project_id,
        name=name,
        description=description,
        file_path=str(file_path),
        row_count=row_count,
        column_count=column_count,
        columns=columns,
        sensitive_attributes=sensitive_list,
        target_column=target_column,
        profile_data=profile_data,
        uploaded_by_id=current_user.id
    )
    
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.DATASET_UPLOAD,
        resource_type=ResourceType.DATASET,
        resource_id=dataset.id,
        details={
            "dataset_name": name,
            "row_count": row_count,
            "column_count": column_count
        }
    )
    db.add(audit)
    await db.commit()
    
    return DatasetResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        description=dataset.description,
        file_path=dataset.file_path,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=dataset.columns or [],
        sensitive_attributes=dataset.sensitive_attributes or [],
        target_column=dataset.target_column,
        uploaded_at=dataset.uploaded_at
    )


@router.get("/project/{project_id}", response_model=List[DatasetResponse])
async def list_datasets(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all datasets in a project."""
    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get datasets
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.uploaded_at.desc())
    )
    datasets = result.scalars().all()
    
    return [
        DatasetResponse(
            id=d.id,
            project_id=d.project_id,
            name=d.name,
            description=d.description,
            file_path=d.file_path,
            row_count=d.row_count,
            column_count=d.column_count,
            columns=d.columns or [],
            sensitive_attributes=d.sensitive_attributes or [],
            target_column=d.target_column,
            uploaded_at=d.uploaded_at
        )
        for d in datasets
    ]


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific dataset by ID."""
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Check project access
    result = await db.execute(
        select(Project).where(Project.id == dataset.project_id)
    )
    project = result.scalar_one_or_none()
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return DatasetResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        description=dataset.description,
        file_path=dataset.file_path,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=dataset.columns or [],
        sensitive_attributes=dataset.sensitive_attributes or [],
        target_column=dataset.target_column,
        uploaded_at=dataset.uploaded_at
    )


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
async def get_dataset_profile(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed profile of a dataset including sample data."""
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Check project access
    result = await db.execute(
        select(Project).where(Project.id == dataset.project_id)
    )
    project = result.scalar_one_or_none()
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Read sample data
    try:
        df = pd.read_csv(dataset.file_path, nrows=10)
        sample_data = df.to_dict(orient="records")
    except Exception:
        sample_data = []
    
    profile = dataset.profile_data or {}
    
    return DatasetProfileResponse(
        id=dataset.id,
        name=dataset.name,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=dataset.columns or [],
        column_types=profile.get("column_types", {}),
        missing_values=profile.get("missing_values", {}),
        unique_counts=profile.get("unique_counts", {}),
        sample_data=sample_data
    )


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a dataset."""
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Check project access
    result = await db.execute(
        select(Project).where(Project.id == dataset.project_id)
    )
    project = result.scalar_one_or_none()
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete file
    try:
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)
    except Exception:
        pass
    
    # Delete record
    await db.delete(dataset)
    await db.commit()
    
    return {"message": "Dataset deleted successfully"}


@router.post("/project/{project_id}/load-benchmark", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def load_benchmark_dataset(
    project_id: UUID,
    dataset_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Load a pre-configured benchmark dataset into a project.
    
    Available datasets:
    - "compas": COMPAS Recidivism dataset (criminal justice)
    - "adult_income": Adult Income/Census dataset (employment fairness)
    - "german_credit": German Credit dataset (financial fairness)
    
    Args:
        project_id: Project to load dataset into
        dataset_key: Key identifying which benchmark dataset to load
    
    Returns:
        Created dataset with metadata
    """
    # Import here to avoid circular imports
    from ..services.dataset_seeder import BenchmarkDatasetSeeder
    
    # Verify project exists and user has access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Load benchmark dataset
    try:
        seeder = BenchmarkDatasetSeeder()
        dataset = await seeder.seed_benchmark_datasets(
            project_id=project_id,
            dataset_key=dataset_key,
            db=db,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Benchmark dataset file not found: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to load benchmark dataset: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load benchmark dataset")
    
    return dataset


@router.get("/benchmark/available")
async def get_available_benchmark_datasets():
    """
    Get list of available benchmark datasets with metadata.
    
    Returns:
        Dictionary of available benchmark datasets with their descriptions
    """
    from ..services.dataset_seeder import BenchmarkDatasetSeeder
    
    seeder = BenchmarkDatasetSeeder()
    datasets = seeder.get_available_datasets()
    
    return {
        "datasets": datasets,
        "count": len(datasets)
    }
